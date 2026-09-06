import { common } from '@kit.AbilityKit';
import { camera } from '@kit.CameraKit';
import { faceDetector } from '@kit.CoreVisionKit';
import { image } from '@kit.ImageKit';
import { mindSporeLite } from '@kit.MindSporeLiteKit';
import { ExpressionRecognitionProvider } from './ExpressionRecognitionProvider';
import { ExpressionModelMath, ExpressionPrediction } from './ExpressionModelMath';
import { ExpressionModelContract } from './ExpressionModelContract';
import {
  ExpressionFaceQuality,
  ExpressionFaceQualityDecision,
  ExpressionPixelQuality
} from './ExpressionFaceQuality';
import { ExpressionSignalProcessor, StableExpressionSignal } from './ExpressionSignalProcessor';

const MODEL_PATH: string = 'models/expression/campusmate_expression_v2.ms';
const MODEL_VERSION: string = 'expression-resnet18-multiv2-v1-mslite';
const INPUT_SIZE: number = 96;
const MIN_FRAME_INTERVAL_MS: number = 450;

/**
 * Local-only Harmony expression pipeline: front camera -> Core Vision face ROI
 * -> MindSpore Lite classifier -> stable label. Pixel buffers never leave this class.
 */
export class MindSporeExpressionProvider implements ExpressionRecognitionProvider {
  private readonly context: common.UIAbilityContext;
  private readonly processor: ExpressionSignalProcessor = new ExpressionSignalProcessor(
    undefined, 0.7, 3, 0.4, 5000, MODEL_VERSION
  );
  private model: mindSporeLite.Model | null = null;
  private cameraInput: camera.CameraInput | null = null;
  private previewOutput: camera.PreviewOutput | null = null;
  private session: camera.PhotoSession | null = null;
  private receiver: image.ImageReceiver | null = null;
  private running: boolean = false;
  private processing: boolean = false;
  private lastFrameAt: number = 0;
  private providerDetail: string = '本地表情模型尚未启动';

  constructor(context: common.UIAbilityContext) {
    this.context = context;
  }

  available(): boolean { return this.running && this.model !== null; }
  latestSignal(): StableExpressionSignal | undefined { return this.processor.latest(); }
  detail(): string { return this.providerDetail; }

  async start(): Promise<void> {
    if (this.running) return;
    try {
      await this.ensureModel();
      const detectorReady: boolean = await faceDetector.init();
      if (!detectorReady) throw new Error('face detector unavailable');
      await this.openFrontCamera();
      this.running = true;
      this.providerDetail = '正在本机识别表情；画面不上传、不保存';
    } catch (error) {
      this.providerDetail = '本地情绪识别不可用，聊天将不附带表情信息';
      await this.releaseCamera();
      try { await faceDetector.release(); } catch (_) { /* already unavailable */ }
      throw new Error('local expression pipeline failed');
    }
  }

  async stop(): Promise<void> {
    this.running = false;
    this.processing = false;
    this.processor.reset();
    await this.releaseCamera();
    try { await faceDetector.release(); } catch (_) { /* safe idempotent cleanup */ }
    this.providerDetail = '情绪识别已停止';
  }

  private async ensureModel(): Promise<void> {
    if (this.model !== null) return;
    const bytes: Uint8Array = await this.context.resourceManager.getRawFileContent(MODEL_PATH);
    const buffer: ArrayBuffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(buffer).set(bytes);
    const loaded: mindSporeLite.Model = await mindSporeLite.loadModelFromBuffer(buffer);
    const inputs: mindSporeLite.MSTensor[] = loaded.getInputs();
    if (inputs.length !== 1 ||
      !ExpressionModelContract.acceptsInput(inputs[0].shape, inputs[0].elementNum)) {
      throw new Error('expression input contract mismatch');
    }
    this.model = loaded;
  }

  private async openFrontCamera(): Promise<void> {
    const manager: camera.CameraManager = camera.getCameraManager(this.context);
    const devices: camera.CameraDevice[] = manager.getSupportedCameras();
    const device: camera.CameraDevice | undefined = devices.find((item: camera.CameraDevice) =>
      item.cameraPosition === camera.CameraPosition.CAMERA_POSITION_FRONT);
    if (device === undefined) throw new Error('front camera unavailable');

    const capability: camera.CameraOutputCapability =
      manager.getSupportedOutputCapability(device, camera.SceneMode.NORMAL_PHOTO);
    const profile: camera.Profile | undefined = this.selectPreviewProfile(capability.previewProfiles);
    if (profile === undefined) throw new Error('preview profile unavailable');

    const receiver: image.ImageReceiver = image.createImageReceiver(profile.size, image.ImageFormat.JPEG, 2);
    const surfaceId: string = await receiver.getReceivingSurfaceId();
    const input: camera.CameraInput = manager.createCameraInput(device);
    const output: camera.PreviewOutput = manager.createPreviewOutput(profile, surfaceId);
    const captureSession: camera.PhotoSession = manager.createSession<camera.PhotoSession>(camera.SceneMode.NORMAL_PHOTO);

    try {
      const rotation: camera.ImageRotation = output.getPreviewRotation(0);
      output.setPreviewRotation(rotation, true);
    } catch (_) {
      // Keep the device default only when the capability is unavailable.
    }

    receiver.on('imageArrival', () => { this.consumeLatestFrame(); });
    await input.open();
    captureSession.beginConfig();
    captureSession.addInput(input);
    captureSession.addOutput(output);
    await captureSession.commitConfig();
    await captureSession.start();

    this.receiver = receiver;
    this.cameraInput = input;
    this.previewOutput = output;
    this.session = captureSession;
  }

  private selectPreviewProfile(profiles: camera.Profile[]): camera.Profile | undefined {
    if (profiles.length === 0) return undefined;
    let selected: camera.Profile = profiles[0];
    let selectedScore: number = Number.MAX_VALUE;
    for (let index: number = 0; index < profiles.length; index++) {
      const profile: camera.Profile = profiles[index];
      const minimumSide: number = Math.min(profile.size.width, profile.size.height);
      const area: number = profile.size.width * profile.size.height;
      const score: number = minimumSide >= 720 ? area : area + 1000000000;
      if (score < selectedScore) {
        selected = profile;
        selectedScore = score;
      }
    }
    return selected;
  }

  private async consumeLatestFrame(): Promise<void> {
    const receiver: image.ImageReceiver | null = this.receiver;
    if (!this.running || receiver === null) return;
    const now: number = Date.now();
    if (this.processing || now - this.lastFrameAt < MIN_FRAME_INTERVAL_MS) return;
    this.processing = true;
    this.lastFrameAt = now;
    let frame: image.Image | null = null;
    try {
      frame = await receiver.readLatestImage();
      const component: image.Component = await frame.getComponent(image.ComponentType.JPEG);
      await this.analyzeJpeg(component.byteBuffer, now);
    } catch (_) {
      this.providerDetail = '正在等待清晰正脸，不会上传相机画面';
    } finally {
      if (frame !== null) {
        try { await frame.release(); } catch (_) { /* release best effort */ }
      }
      this.processing = false;
    }
  }

  private async analyzeJpeg(buffer: ArrayBuffer, timestamp: number): Promise<void> {
    const source: image.ImageSource = image.createImageSource(buffer);
    let full: image.PixelMap | null = null;
    let faceCrop: image.PixelMap | null = null;
    try {
      full = await source.createPixelMap({ desiredPixelFormat: image.PixelMapFormat.RGBA_8888 });
      const faces: faceDetector.Face[] = await faceDetector.detect({ pixelMap: full });
      if (faces.length > 1) {
        this.processor.push({ label: 'NO_FACE', confidence: 0, timestamp: timestamp });
        this.providerDetail = '检测到多人，出于隐私与准确性暂不识别表情';
        return;
      }
      const face: faceDetector.Face | undefined = this.largestFace(faces);
      if (face === undefined) {
        this.processor.push({ label: 'NO_FACE', confidence: 0, timestamp: timestamp });
        this.providerDetail = '未检测到正脸，暂不向 AI 提供情绪信息';
        return;
      }
      const size: image.Size = full.getImageInfoSync().size;
      const region: image.Region = this.paddedRegion(face.rect, size.width, size.height);
      faceCrop = await source.createPixelMap({
        desiredRegion: region,
        desiredSize: { width: INPUT_SIZE, height: INPUT_SIZE },
        desiredPixelFormat: image.PixelMapFormat.RGBA_8888
      });
      const rgbaBuffer: ArrayBuffer = new ArrayBuffer(INPUT_SIZE * INPUT_SIZE * 4);
      await faceCrop.readPixelsToBuffer(rgbaBuffer);
      const rgbaPixels: Uint8Array = new Uint8Array(rgbaBuffer);
      const pixelQuality: ExpressionPixelQuality = ExpressionFaceQuality.measureRgba(
        rgbaPixels, INPUT_SIZE, INPUT_SIZE
      );
      const faceRatio: number = Math.min(region.size.width, region.size.height) /
        Math.max(1, Math.min(size.width, size.height));
      const quality: ExpressionFaceQualityDecision = ExpressionFaceQuality.evaluate({
        faceCount: faces.length,
        faceRatio: faceRatio,
        sharpness: pixelQuality.sharpness,
        brightness: pixelQuality.brightness
      });
      if (!quality.accepted) {
        this.processor.push({ label: 'NO_FACE', confidence: 0, timestamp: timestamp });
        this.providerDetail = '正在等待清晰、光线合适的单人正脸';
        return;
      }
      const inputData: Float32Array | undefined = ExpressionModelMath.rgbaToGrayscaleNhwc(
        rgbaPixels, INPUT_SIZE, INPUT_SIZE
      );
      if (inputData === undefined) throw new Error('expression preprocessing failed');
      const prediction: ExpressionPrediction | undefined = await this.predict(inputData);
      if (prediction === undefined) throw new Error('expression output contract mismatch');
      this.processor.push({ label: prediction.label, confidence: prediction.confidence, timestamp: timestamp });
      this.providerDetail = this.processor.latest(timestamp) === undefined ?
        '正在本机确认稳定表情，不上传画面' : '已获得稳定表情标签，仅标签会随提问发送';
    } finally {
      if (faceCrop !== null) await faceCrop.release();
      if (full !== null) await full.release();
      await source.release();
    }
  }

  private async predict(inputData: Float32Array): Promise<ExpressionPrediction | undefined> {
    const model: mindSporeLite.Model | null = this.model;
    if (model === null) return undefined;
    const inputs: mindSporeLite.MSTensor[] = model.getInputs();
    inputs[0].setData(inputData.buffer);
    const outputs: mindSporeLite.MSTensor[] = await model.predict(inputs);
    if (outputs.length !== 1) return undefined;
    const data: ArrayBuffer = outputs[0].getData();
    if (!ExpressionModelContract.acceptsOutput(outputs[0].shape, outputs[0].elementNum, data.byteLength)) {
      return undefined;
    }
    return ExpressionModelMath.decode(new Float32Array(data));
  }

  private largestFace(faces: faceDetector.Face[]): faceDetector.Face | undefined {
    let selected: faceDetector.Face | undefined = undefined;
    let selectedArea: number = 0;
    for (let index: number = 0; index < faces.length; index++) {
      const area: number = faces[index].rect.width * faces[index].rect.height;
      if (area > selectedArea) {
        selected = faces[index];
        selectedArea = area;
      }
    }
    return selected;
  }

  private paddedRegion(rect: faceDetector.FaceRectangle, width: number, height: number): image.Region {
    const left: number = Math.max(0, Math.floor(rect.left - rect.width * 0.16));
    const top: number = Math.max(0, Math.floor(rect.top - rect.height * 0.20));
    const right: number = Math.min(width, Math.ceil(rect.left + rect.width * 1.16));
    const bottom: number = Math.min(height, Math.ceil(rect.top + rect.height * 1.20));
    return { x: left, y: top, size: { width: Math.max(1, right - left), height: Math.max(1, bottom - top) } };
  }

  private async releaseCamera(): Promise<void> {
    const session: camera.PhotoSession | null = this.session;
    const output: camera.PreviewOutput | null = this.previewOutput;
    const input: camera.CameraInput | null = this.cameraInput;
    const receiver: image.ImageReceiver | null = this.receiver;
    this.session = null;
    this.previewOutput = null;
    this.cameraInput = null;
    this.receiver = null;
    if (receiver !== null) receiver.off('imageArrival');
    if (session !== null) {
      try { await session.stop(); } catch (_) { /* already stopped */ }
      try { await session.release(); } catch (_) { /* already released */ }
    }
    if (output !== null) {
      try { await output.release(); } catch (_) { /* already released */ }
    }
    if (input !== null) {
      try { await input.close(); } catch (_) { /* already closed */ }
    }
    if (receiver !== null) {
      try { await receiver.release(); } catch (_) { /* already released */ }
    }
  }
}

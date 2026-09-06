import { abilityAccessCtrl, common, PermissionRequestResult, Permissions } from '@kit.AbilityKit';
import { camera } from '@kit.CameraKit';
import { image } from '@kit.ImageKit';
import { objectDetection, visionBase } from '@kit.CoreVisionKit';
import { FocusAssistProvider, FocusAssistStatus, RgbaBehaviorFrame } from './FocusAssistProvider';
import {
  DetectionCandidate,
  DetectionBoundingBox,
  FocusCameraState,
  FocusCameraStateText,
  FocusCameraRunToken,
  FrameAnalysisGate,
  ImageArrivalGate,
  PersonAbsenceTracker,
  PersonBox,
  PersonRoiSelector
} from './FocusCameraContract';

export class FocusCameraPipeline {
  private readonly context: common.UIAbilityContext;
  private readonly provider: FocusAssistProvider;
  private readonly onUpdate: () => void;
  private readonly frameGate: FrameAnalysisGate = new FrameAnalysisGate();
  private readonly imageArrivalGate: ImageArrivalGate = new ImageArrivalGate();
  private readonly absenceTracker: PersonAbsenceTracker = new PersonAbsenceTracker();
  private readonly runToken: FocusCameraRunToken = new FocusCameraRunToken();
  private pipelineState: string = FocusCameraState.STOPPED;
  private running: boolean = false;
  private cameraInput: camera.CameraInput | undefined = undefined;
  private previewOutput: camera.PreviewOutput | undefined = undefined;
  private session: camera.VideoSession | undefined = undefined;
  private receiver: image.ImageReceiver | undefined = undefined;
  private detector: objectDetection.ObjectDetector | undefined = undefined;
  private analysisTask: Promise<void> | undefined = undefined;
  private startTask: Promise<void> | undefined = undefined;
  private stopTask: Promise<void> | undefined = undefined;

  constructor(context: common.UIAbilityContext, provider: FocusAssistProvider, onUpdate: () => void) {
    this.context = context;
    this.provider = provider;
    this.onUpdate = onUpdate;
  }

  state(): string {
    return this.pipelineState;
  }

  detail(): string {
    if (this.pipelineState === FocusCameraState.RUNNING) return this.provider.detail();
    return FocusCameraStateText.describe(this.pipelineState);
  }

  isRunning(): boolean {
    return this.running;
  }

  async start(): Promise<void> {
    if (this.running) return;
    const stopping: Promise<void> | undefined = this.stopTask;
    if (stopping !== undefined) await stopping;
    const existing: Promise<void> | undefined = this.startTask;
    if (existing !== undefined) {
      await existing;
      return;
    }
    const version: number = this.runToken.beginStart();
    const task: Promise<void> = this.startInternal(version);
    this.startTask = task;
    try {
      await task;
    } finally {
      if (this.startTask === task) this.startTask = undefined;
    }
  }

  private async startInternal(version: number): Promise<void> {
    this.setState(FocusCameraState.STARTING);
    try {
      const granted: boolean = await this.requestCameraPermission();
      this.ensureCurrent(version);
      if (!granted) {
        this.setState(FocusCameraState.PERMISSION_DENIED);
        return;
      }
      await this.provider.start();
      this.ensureCurrent(version);
      if (this.provider.status() === FocusAssistStatus.ERROR) {
        await this.cleanupFailedStart();
        this.setState(FocusCameraState.UNAVAILABLE);
        return;
      }
      this.detector = await objectDetection.ObjectDetector.create();
      this.ensureCurrent(version);
      const manager: camera.CameraManager = camera.getCameraManager(this.context);
      const devices: camera.CameraDevice[] = manager.getSupportedCameras();
      const device: camera.CameraDevice | undefined = this.selectCamera(devices);
      if (device === undefined) throw new Error('No camera available');
      const capability: camera.CameraOutputCapability =
        manager.getSupportedOutputCapability(device, camera.SceneMode.NORMAL_VIDEO);
      const profile: camera.Profile | undefined = this.selectProfile(capability.previewProfiles);
      if (profile === undefined) throw new Error('No preview profile available');

      this.receiver = image.createImageReceiver(profile.size, image.ImageFormat.JPEG, 3);
      const surfaceId: string = await this.receiver.getReceivingSurfaceId();
      this.previewOutput = manager.createPreviewOutput(profile, surfaceId);
      try {
        const rotation: camera.ImageRotation = this.previewOutput.getPreviewRotation(0);
        this.previewOutput.setPreviewRotation(rotation, true);
      } catch (_) {
        // Older supported devices can keep their default preview rotation.
      }
      this.cameraInput = manager.createCameraInput(device);
      await this.cameraInput.open();
      this.ensureCurrent(version);
      this.session = manager.createSession(camera.SceneMode.NORMAL_VIDEO) as camera.VideoSession;
      this.session.beginConfig();
      if (!this.session.canAddInput(this.cameraInput)) throw new Error('Camera input rejected');
      this.session.addInput(this.cameraInput);
      if (!this.session.canAddOutput(this.previewOutput)) throw new Error('Preview output rejected');
      this.session.addOutput(this.previewOutput);
      await this.session.commitConfig();
      this.ensureCurrent(version);
      this.receiver.on('imageArrival', () => this.onImageArrival());
      await this.session.start();
      this.ensureCurrent(version);
      this.running = true;
      this.frameGate.reset();
      this.setState(FocusCameraState.WAITING_FOR_PERSON);
    } catch (_) {
      await this.cleanupFailedStart();
      if (this.runToken.isCurrent(version)) this.setState(FocusCameraState.UNAVAILABLE);
    }
  }

  async stop(): Promise<void> {
    this.runToken.stop();
    this.running = false;
    this.absenceTracker.suspend();
    const existing: Promise<void> | undefined = this.stopTask;
    if (existing !== undefined) {
      await existing;
      return;
    }
    const task: Promise<void> = this.stopInternal();
    this.stopTask = task;
    try {
      await task;
    } finally {
      if (this.stopTask === task) this.stopTask = undefined;
    }
  }

  private async stopInternal(): Promise<void> {
    // stop() invalidates the provider synchronously before any wait, freezing the aggregate snapshot.
    const providerStop: Promise<void> = this.provider.stop();
    const starting: Promise<void> | undefined = this.startTask;
    if (starting !== undefined) await starting.catch(() => {});
    await providerStop;
    await this.releaseResources();
    this.frameGate.reset();
    this.setState(FocusCameraState.STOPPED);
  }

  private async cleanupFailedStart(): Promise<void> {
    this.running = false;
    await this.provider.stop().catch(() => {});
    await this.releaseResources();
    this.frameGate.reset();
  }

  resetSession(): void {
    this.absenceTracker.reset();
  }

  private ensureCurrent(version: number): void {
    if (!this.runToken.isCurrent(version)) throw new Error('Camera start cancelled');
  }

  private async requestCameraPermission(): Promise<boolean> {
    const permissions: Permissions[] = ['ohos.permission.CAMERA'];
    const result: PermissionRequestResult = await abilityAccessCtrl.createAtManager()
      .requestPermissionsFromUser(this.context, permissions);
    return result.authResults.length === 1 && result.authResults[0] === 0;
  }

  private selectCamera(devices: camera.CameraDevice[]): camera.CameraDevice | undefined {
    const front: camera.CameraDevice | undefined = devices.find((device: camera.CameraDevice) =>
      device.cameraPosition === camera.CameraPosition.CAMERA_POSITION_FRONT);
    return front ?? devices[0];
  }

  private selectProfile(profiles: camera.Profile[]): camera.Profile | undefined {
    if (profiles.length === 0) return undefined;
    const minimumArea: number = 1280 * 720;
    let bestAtLeast720p: camera.Profile | undefined = undefined;
    let largest: camera.Profile = profiles[0];
    for (const profile of profiles) {
      const area: number = profile.size.width * profile.size.height;
      const largestArea: number = largest.size.width * largest.size.height;
      if (area > largestArea) largest = profile;
      if (area >= minimumArea && (bestAtLeast720p === undefined ||
        area < bestAtLeast720p.size.width * bestAtLeast720p.size.height)) {
        bestAtLeast720p = profile;
      }
    }
    return bestAtLeast720p ?? largest;
  }

  private onImageArrival(): void {
    const receiver: image.ImageReceiver | undefined = this.receiver;
    if (receiver === undefined || !this.imageArrivalGate.tryAcquire()) return;
    receiver.readLatestImage().then((cameraImage: image.Image) => {
      const timestamp: number = Date.now();
      if (!this.running || !this.frameGate.tryAcquire(timestamp)) {
        cameraImage.release().catch(() => {});
        return;
      }
      const task: Promise<void> = this.processFrame(cameraImage, timestamp);
      this.analysisTask = task;
      task.finally(() => {
        this.frameGate.release();
        if (this.analysisTask === task) this.analysisTask = undefined;
      });
    }).catch(() => {
      if (this.running) this.setState(FocusCameraState.ERROR);
    }).finally(() => {
      this.imageArrivalGate.release();
    });
  }

  private async processFrame(cameraImage: image.Image, timestamp: number): Promise<void> {
    let source: image.ImageSource | undefined = undefined;
    let pixelMap: image.PixelMap | undefined = undefined;
    try {
      const component: image.Component = await cameraImage.getComponent(image.ComponentType.JPEG);
      source = image.createImageSource(component.byteBuffer);
      pixelMap = await source.createPixelMap({ desiredPixelFormat: image.PixelMapFormat.RGBA_8888 });
      const info: image.ImageInfo = await pixelMap.getImageInfo();
      const detector: objectDetection.ObjectDetector | undefined = this.detector;
      if (!this.running || detector === undefined) return;
      const request: visionBase.Request = {
        inputData: { pixelMap: pixelMap },
        scene: visionBase.SceneMode.FOREGROUND
      };
      const response: objectDetection.ObjectDetectionResponse = await detector.process(request);
      const candidates: DetectionCandidate[] = [];
      for (const item of response.objects) {
        const boundingBox: DetectionBoundingBox = {
          left: item.boundingBox.left,
          top: item.boundingBox.top,
          width: item.boundingBox.width,
          height: item.boundingBox.height
        };
        const candidate: DetectionCandidate = {
          labels: item.labels,
          score: item.score,
          boundingBox: boundingBox
        };
        candidates.push(candidate);
      }
      const personBox: PersonBox | undefined = PersonRoiSelector.select(
        candidates, info.size.width, info.size.height);
      if (!this.running) return;
      if (personBox === undefined) {
        if (this.absenceTracker.process(false, timestamp)) this.provider.recordAbsence();
        this.setState(FocusCameraState.WAITING_FOR_PERSON);
        return;
      }
      this.absenceTracker.process(true, timestamp);
      const rgbaBuffer: ArrayBuffer = new ArrayBuffer(info.size.width * info.size.height * 4);
      await pixelMap.readPixelsToBuffer(rgbaBuffer);
      const behaviorFrame: RgbaBehaviorFrame = {
        pixels: new Uint8Array(rgbaBuffer),
        width: info.size.width,
        height: info.size.height,
        personBox: personBox,
        timestamp: timestamp
      };
      await this.provider.analyze(behaviorFrame);
      if (!this.running) return;
      const providerStatus: FocusAssistStatus = this.provider.status();
      if (providerStatus === FocusAssistStatus.RUNNING) {
        // The state may be unchanged while the latest aggregate signal has changed.
        this.setState(FocusCameraState.RUNNING, true);
      } else if (providerStatus === FocusAssistStatus.ERROR) {
        this.setState(FocusCameraState.ERROR);
      } else {
        this.setState(FocusCameraState.UNAVAILABLE);
      }
    } catch (_) {
      if (this.running) this.setState(FocusCameraState.ERROR);
    } finally {
      if (pixelMap !== undefined) await pixelMap.release().catch(() => {});
      if (source !== undefined) await source.release().catch(() => {});
      await cameraImage.release().catch(() => {});
    }
  }

  private async releaseResources(): Promise<void> {
    if (this.receiver !== undefined) {
      try { this.receiver.off('imageArrival'); } catch (_) {}
    }
    const task: Promise<void> | undefined = this.analysisTask;
    if (task !== undefined) await task.catch(() => {});
    if (this.session !== undefined) await this.session.stop().catch(() => {});
    if (this.cameraInput !== undefined) await this.cameraInput.close().catch(() => {});
    if (this.previewOutput !== undefined) await this.previewOutput.release().catch(() => {});
    if (this.session !== undefined) await this.session.release().catch(() => {});
    if (this.receiver !== undefined) await this.receiver.release().catch(() => {});
    if (this.detector !== undefined) await this.detector.destroy().catch(() => {});
    this.cameraInput = undefined;
    this.previewOutput = undefined;
    this.session = undefined;
    this.receiver = undefined;
    this.detector = undefined;
    this.analysisTask = undefined;
    this.imageArrivalGate.release();
  }

  private setState(state: string, forceUpdate: boolean = false): void {
    const changed: boolean = this.pipelineState !== state;
    this.pipelineState = state;
    if (changed || forceUpdate) this.onUpdate();
  }
}

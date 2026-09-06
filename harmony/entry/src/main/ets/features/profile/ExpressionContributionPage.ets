import { common } from '@kit.AbilityKit';
import picker from '@ohos.file.picker';
import { ExpressionContributionRepository } from '../../repository/ExpressionContributionRepository';
import { ExpressionContributionResponse } from '../../data/Models';
import { ApiClient } from '../../data/ApiClient';

const EXPRESSION_LABELS: string[] = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise'];
const LABEL_DISPLAY: Record<string, string> = {
  'angry': '愤怒', 'disgust': '厌恶', 'fear': '恐惧', 'happy': '开心',
  'neutral': '中性', 'sad': '悲伤', 'surprise': '惊讶'
};

interface UploadedSample {
  sampleId: string;
  label: string;
  status: string;
  message: string;
}

@Builder
function ExpressionLabelChip(label: string, selected: boolean, onTap: (label: string) => void) {
  Text(LABEL_DISPLAY[label] ?? label)
    .fontSize(14)
    .fontColor(selected ? '#FFFFFFFF' : '#333333')
    .backgroundColor(selected ? '#3B82F6' : '#F3F4F6')
    .borderRadius(16)
    .padding({ left: 12, right: 12, top: 6, bottom: 6 })
    .margin({ right: 8, bottom: 8 })
    .onClick(() => onTap(label))
}

@Component
export struct ExpressionContributionPage {
  private context: common.UIAbilityContext = getContext(this) as common.UIAbilityContext;
  @Prop authToken: string = '';
  @Prop apiBaseUrl: string = '';
  @State selectedLabel: string = 'happy';
  @State selectedFileUri: string = '';
  @State selectedFileName: string = '';
  @State uploading: boolean = false;
  @State uploadMessage: string = '';
  @State uploadError: string = '';
  @State uploadedSamples: UploadedSample[] = [];
  @State refreshing: boolean = false;

  private createRepository(): ExpressionContributionRepository | null {
    if (this.authToken.length === 0 || this.apiBaseUrl.length === 0) return null;
    const client: ApiClient = new ApiClient(this.apiBaseUrl, () => this.authToken);
    return new ExpressionContributionRepository(client);
  }

  async pickImage(): Promise<void> {
    try {
      const photoPicker: picker.PhotoViewPicker = new picker.PhotoViewPicker();
      const result: picker.PhotoSelectResult = await photoPicker.select({
        maxSelectNumber: 1,
        selectMode: picker.PhotoViewPickerSelectMode.PHOTO_SELECT
      } as picker.PhotoSelectOptions);
      if (result.photoUris.length > 0) {
        this.selectedFileUri = result.photoUris[0];
        const parts: string[] = result.photoUris[0].split('/');
        this.selectedFileName = parts[parts.length - 1] || 'image.jpg';
        this.uploadError = '';
      }
    } catch (_) {
      this.uploadError = '选择图片失败，请重试';
    }
  }

  async uploadSample(): Promise<void> {
    if (this.selectedFileUri.length === 0) {
      this.uploadError = '请先选择一张表情图片';
      return;
    }
    const repository: ExpressionContributionRepository | null = this.createRepository();
    if (repository === null) {
      this.uploadError = '未登录，无法上传';
      return;
    }
    this.uploading = true;
    this.uploadError = '';
    this.uploadMessage = '';
    try {
      const response: ExpressionContributionResponse = await repository.upload(
        this.selectedFileUri, this.selectedFileName, 'image/jpeg', this.selectedLabel
      );
      this.uploadMessage = response.message.length > 0 ? response.message : '上传成功，感谢贡献';
      this.uploadedSamples = [{
        sampleId: response.sample_id,
        label: response.label,
        status: response.status,
        message: response.message
      }, ...this.uploadedSamples];
      this.selectedFileUri = '';
      this.selectedFileName = '';
    } catch (error) {
      this.uploadError = error instanceof Error ? error.message : '上传失败，请检查网络后重试';
    } finally {
      this.uploading = false;
    }
  }

  async deleteSample(sampleId: string): Promise<void> {
    const repository: ExpressionContributionRepository | null = this.createRepository();
    if (repository === null) return;
    try {
      await repository.delete(sampleId);
      this.uploadedSamples = this.uploadedSamples.filter((s: UploadedSample): boolean => s.sampleId !== sampleId);
    } catch (_) {
      this.uploadError = '删除失败，请稍后重试';
    }
  }

  build() {
    Column() {
      Text('表情样本共建')
        .fontSize(22)
        .fontWeight(FontWeight.Bold)
        .margin({ bottom: 16 })

      Text('拍摄或选择一张表情图片，标注后上传，帮助改进校园情绪识别模型。图片将用于模型训练，不会关联到你的账号。')
        .fontSize(13)
        .fontColor('#666666')
        .margin({ bottom: 20 })

      Text('选择表情标签')
        .fontSize(15)
        .fontWeight(FontWeight.Medium)
        .margin({ bottom: 8 })
      Flex({ wrap: FlexWrap.Wrap }) {
        ForEach(EXPRESSION_LABELS, (label: string) => {
          ExpressionLabelChip(label, label === this.selectedLabel, (tapped: string) => {
            this.selectedLabel = tapped;
          })
        })
      }
      .margin({ bottom: 20 })

      Button(this.selectedFileUri.length > 0 ? this.selectedFileName : '选择图片')
        .width('100%')
        .type(ButtonType.Capsule)
        .backgroundColor('#F3F4F6')
        .fontColor('#333333')
        .onClick(() => this.pickImage())
        .margin({ bottom: 12 })

      Button('上传样本')
        .width('100%')
        .type(ButtonType.Capsule)
        .backgroundColor('#3B82F6')
        .fontColor('#FFFFFF')
        .enabled(!this.uploading && this.selectedFileUri.length > 0)
        .onClick(() => this.uploadSample())
        .margin({ bottom: 12 })

      if (this.uploadMessage.length > 0) {
        Text(this.uploadMessage)
          .fontSize(13)
          .fontColor('#16A34A')
          .margin({ bottom: 8 })
      }
      if (this.uploadError.length > 0) {
        Text(this.uploadError)
          .fontSize(13)
          .fontColor('#DC2626')
          .margin({ bottom: 8 })
      }

      if (this.uploadedSamples.length > 0) {
        Text('已上传样本')
          .fontSize(15)
          .fontWeight(FontWeight.Medium)
          .margin({ top: 12, bottom: 8 })
        List() {
          ForEach(this.uploadedSamples, (sample: UploadedSample) => {
            ListItem() {
              Row() {
                Column() {
                  Text(`${LABEL_DISPLAY[sample.label] ?? sample.label} · ${sample.status}`)
                    .fontSize(14)
                    .fontColor('#333333')
                  if (sample.message.length > 0) {
                    Text(sample.message)
                      .fontSize(12)
                      .fontColor('#999999')
                      .margin({ top: 2 })
                  }
                }
                .alignItems(HorizontalAlign.Start)
                .layoutWeight(1)
                Button('删除')
                  .fontSize(12)
                  .type(ButtonType.Capsule)
                  .backgroundColor('#FEE2E2')
                  .fontColor('#DC2626')
                  .onClick(() => this.deleteSample(sample.sampleId))
              }
              .width('100%')
              .padding({ top: 8, bottom: 8 })
            }
          })
        }
        .width('100%')
        .layoutWeight(1)
      }
    }
    .width('100%')
    .height('100%')
    .padding({ left: 20, right: 20, top: 20, bottom: 20 })
    .alignItems(HorizontalAlign.Start)
  }
}
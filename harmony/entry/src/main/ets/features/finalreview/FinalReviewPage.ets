import { AgentRuntimeRepository } from '../../repository/AgentRuntimeRepository';
import { FinalReviewCampaign } from '../../data/AgentRuntimeModels';
import { ExamItem } from '../../data/Models';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';

// 期末复习入口：列出已有 campaign，选择考试与每日时长创建新 campaign。
// 考试 ID 使用现有 /student/exams 的字符串 ID，客户端不生成计划。
@Component
export struct FinalReviewPage {
  @Prop exams: ExamItem[] = [];
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  repository: AgentRuntimeRepository | null = null;
  onBack: () => void = () => {};
  onOpenPlan: (campaignId: string) => void = (_: string) => {};
  @State campaigns: FinalReviewCampaign[] = [];
  @State selectedExamIds: string[] = [];
  @State dailyCapacity: number = 120;
  @State loading: boolean = false;
  @State submitting: boolean = false;
  @State error: string = '';
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  async aboutToAppear(): Promise<void> {
    await this.refreshCampaigns();
  }

  async refreshCampaigns(): Promise<void> {
    if (this.repository === null || this.loading) return;
    this.loading = true;
    this.error = '';
    try {
      this.campaigns = await this.repository.listCampaigns();
    } catch (_) {
      this.error = '加载复习计划失败，请下拉重试';
    } finally {
      this.loading = false;
    }
  }

  toggleExam(examId: string): void {
    if (this.selectedExamIds.indexOf(examId) >= 0) {
      this.selectedExamIds = this.selectedExamIds.filter((id: string) => id !== examId);
    } else {
      this.selectedExamIds = [...this.selectedExamIds, examId];
    }
  }

  async createCampaign(): Promise<void> {
    if (this.repository === null || this.submitting) return;
    if (this.selectedExamIds.length === 0) {
      this.error = '请至少选择一门考试';
      return;
    }
    this.submitting = true;
    this.error = '';
    try {
      const campaign: FinalReviewCampaign = await this.repository.createCampaign(
        this.selectedExamIds, this.dailyCapacity);
      this.selectedExamIds = [];
      await this.refreshCampaigns();
      this.onOpenPlan(campaign.campaign_id);
    } catch (_) {
      this.error = '创建复习计划失败，请重试';
    } finally {
      this.submitting = false;
    }
  }

  statusLabel(status: string): string {
    switch (status.toLowerCase()) {
      case 'active': return '已激活';
      case 'draft': return '待生成';
      case 'completed': return '已完成';
      case 'cancelled': return '已取消';
      default: return '进行中';
    }
  }

  build() {
    Column() {
      SecondaryHeader({ title: '期末复习', subtitle: '版本化计划与每日跟进', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 14 }) {
          if (this.error.length > 0) {
            Text(this.error).fontColor(this.palette().danger).fontSize(12)
          }

          Text('选择考试').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium)
          if (this.exams.length === 0) {
            Text('暂无考试安排，请先在考试页确认。').fontColor(this.palette().muted).fontSize(12)
          } else {
            ForEach(this.exams, (exam: ExamItem) => {
              Row({ space: 10 }) {
                Checkbox()
                  .select(this.selectedExamIds.indexOf(exam.id) >= 0)
                  .onChange((value: boolean) => this.toggleExam(exam.id))
                Column({ space: 2 }) {
                  Text(exam.course_name).fontColor(this.palette().text).fontSize(14).maxLines(1)
                  Text(`${exam.exam_date ?? '日期待定'}`).fontColor(this.palette().muted).fontSize(11)
                }.layoutWeight(1).alignItems(HorizontalAlign.Start)
              }.width('100%').padding(12)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(14)
            }, (exam: ExamItem) => exam.id)
          }

          Row({ space: 10 }) {
            Text('每日可用时长（分钟）').fontColor(this.palette().text).fontSize(13).layoutWeight(1)
            Text(`${this.dailyCapacity}`).fontColor(this.palette().primary).fontSize(15).fontWeight(FontWeight.Bold)
          }.width('100%')
          Slider({ value: this.dailyCapacity, min: 30, max: 300, step: 15 })
            .width('100%').trackColor(this.palette().line).selectedColor(this.palette().primary)
            .onChange((value: number) => { this.dailyCapacity = Math.round(value); })

          Button(this.submitting ? '创建中…' : '创建复习计划')
            .width('100%').height(48)
            .backgroundColor(this.palette().primary).fontColor('#FFFFFF').borderRadius(14)
            .enabled(!this.submitting && this.selectedExamIds.length > 0)
            .onClick(() => this.createCampaign())

          if (this.campaigns.length > 0) {
            Text('已有计划').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Medium).margin({ top: 8 })
            ForEach(this.campaigns, (campaign: FinalReviewCampaign) => {
              Row({ space: 10 }) {
                Column({ space: 3 }) {
                  Text(`计划 ${campaign.campaign_id.substring(0, 12)}`).fontColor(this.palette().text).fontSize(14).maxLines(1)
                  Text(`${campaign.exam_ids.length} 门考试 · ${campaign.daily_capacity_minutes} 分钟/天`)
                    .fontColor(this.palette().muted).fontSize(11)
                }.layoutWeight(1).alignItems(HorizontalAlign.Start)
                Text(this.statusLabel(campaign.status)).fontColor(this.palette().primary).fontSize(12)
                SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(16).fontColor([this.palette().muted])
              }.width('100%').padding(14)
              .backgroundColor(this.palette().glass.surface).border({ width: 1, color: this.palette().glass.border }).borderRadius(16)
              .onClick(() => this.onOpenPlan(campaign.campaign_id))
            }, (campaign: FinalReviewCampaign) => campaign.campaign_id)
          }
        }.width('100%').padding({ left: 16, right: 16, bottom: 24 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

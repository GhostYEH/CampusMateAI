import { EduScheduleItemDto } from '../../data/ApiClient';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { buildDetailRows, buildExtraRows, ScheduleDetailRow } from './EduSchedulePage';

@Component
export struct EduScheduleDetailPage {
  @Prop item: EduScheduleItemDto = {};
  @Prop darkMode: boolean = false;
  @State detailRows: ScheduleDetailRow[] = [];
  @State detailExtraRows: ScheduleDetailRow[] = [];
  onBack: () => void = () => {};

  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  aboutToAppear(): void {
    this.detailRows = buildDetailRows(this.item);
    this.detailExtraRows = buildExtraRows(this.item.extra_info);
  }

  @Builder DetailRows(rows: ScheduleDetailRow[], prefix: string) {
    ForEach(rows, (row: ScheduleDetailRow) => {
      Row({ space: 12 }) {
        Text(row.label).fontSize(12).fontColor(this.palette().muted).width(80)
        Text(row.value).fontSize(13).fontWeight(FontWeight.Medium).fontColor(this.palette().text).layoutWeight(1)
          .maxLines(3).textOverflow({ overflow: TextOverflow.Ellipsis })
      }.width('100%')
    }, (row: ScheduleDetailRow) => prefix + row.label)
  }

  build() {
    Column() {
      SecondaryHeader({ title: this.item.course_name || '课程详情', subtitle: '查看教务系统课程信息', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 10 }) {
          if ((this.item.course_code || '').length > 0) {
            Text(this.item.course_code || '').fontSize(12).fontColor(this.palette().muted)
          }
          this.DetailRows(this.detailRows, '')
          if (this.detailExtraRows.length > 0) {
            Text('更多信息').fontSize(13).fontWeight(FontWeight.Bold).fontColor(this.palette().text)
            this.DetailRows(this.detailExtraRows, 'extra_')
          }
          Text('数据来源：学校教务系统').fontSize(10).fontColor(this.palette().muted)
        }.width('100%').padding({ left: 22, right: 22, top: 16, bottom: 28 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off).backgroundColor(this.palette().glass.surface).backdropBlur(this.palette().glass.backdropBlur).border({ width: 1, color: this.palette().glass.highlight }).shadow({ radius: 16, color: this.palette().glass.shadow, offsetY: 4 })
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

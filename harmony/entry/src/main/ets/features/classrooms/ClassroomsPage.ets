import { ClassroomAvailability } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';

@Component
export struct ClassroomsPage {
  @Prop classrooms: ClassroomAvailability[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @State slot: string = '1-2节';
  @State capacity: string = '全部容量';
  @State multimedia: boolean = true;
  onBack: () => void = () => {};
  onQuery: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }

  @Builder Chip(label: string, active: boolean, onTap: () => void) {
    Text(label).layoutWeight(1).textAlign(TextAlign.Center).maxLines(1).fontSize(9)
      .fontColor(active ? '#FFFFFFFF' : this.palette().muted).padding({ top: 8, bottom: 8 })
      .backgroundColor(active ? this.palette().primary : this.palette().surface)
      .border({ width: 1, color: active ? this.palette().primary : this.palette().line }).borderRadius(16).onClick(onTap)
  }

  @Builder FilterPanel() {
    Column({ space: 12 }) {
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.clock')).fontSize(18).fontColor([this.palette().primary])
        Text('节次').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
      }.width('100%')
      Row({ space: 6 }) {
        ForEach(['1-2节','3-4节','5-6节','7-8节'], (item: string) => { this.Chip(item, this.slot === item, () => this.slot = item) })
      }.width('100%')
      Divider().color(this.palette().line)
      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.person_2')).fontSize(18).fontColor([this.palette().primary])
        Text('容量').fontColor(this.palette().text).fontSize(15).fontWeight(FontWeight.Bold)
      }.width('100%')
      Row({ space: 6 }) {
        ForEach(['全部容量','>=40座','>=80座','>=100座'], (item: string) => { this.Chip(item, this.capacity === item, () => this.capacity = item) })
      }.width('100%')
      Divider().color(this.palette().line)
      Row({ space: 10 }) {
        SymbolGlyph($r('sys.symbol.computer')).fontSize(20).fontColor([this.palette().primary])
        Column({ space: 2 }) {
          Text('仅显示有多媒体设备').fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold)
          Text('投影、音响等教学设备').fontColor(this.palette().muted).fontSize(10)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Toggle({ type: ToggleType.Switch, isOn: this.multimedia }).onChange((value: boolean) => this.multimedia = value)
      }.width('100%')
    }.width('100%').padding(14).backgroundColor(this.palette().surface)
      .border({ width: 1, color: this.palette().line }).borderRadius(18)
  }

  @Builder ClassroomCard(item: ClassroomAvailability) {
    Row({ space: 12 }) {
      Image($r('app.media.hero_classroom')).width(105).height(78).objectFit(ImageFit.Cover).borderRadius(12)
      Column({ space: 6 }) {
        Text(item.classroom?.name ?? item.name ?? '教室').fontColor(this.palette().text).fontSize(16).fontWeight(FontWeight.Bold)
        Text(`${item.classroom?.building ?? item.building ?? '教学楼'}  ·  ${item.classroom?.capacity ?? item.capacity ?? 0} 座`)
          .fontColor(this.palette().muted).fontSize(10)
        Row({ space: 5 }) {
          Text(this.slot).fontColor(this.palette().primary).fontSize(9).padding({ left: 7, right: 7, top: 4, bottom: 4 }).backgroundColor(this.palette().soft).borderRadius(10)
          if ((item.classroom?.has_multimedia ?? item.has_multimedia) !== false) {
            Text('多媒体').fontColor(this.palette().success).fontSize(9).padding({ left: 7, right: 7, top: 4, bottom: 4 }).backgroundColor('#FFEAF9F3').borderRadius(10)
          }
        }
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      SymbolGlyph($r('sys.symbol.checkmark_circle')).fontSize(18).fontColor([this.palette().success])
    }.width('100%').padding(11).backgroundColor(this.palette().surface).borderRadius(18)
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: 20 })))

  }

  build() {
    Column() {
      SecondaryHeader({ title: '空教室查询', subtitle: '基于课程占用数据，帮你快速找到可用教室', darkMode: this.darkMode, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 13 }) {
          Image($r('app.media.hero_classroom')).width('100%').height(170).objectFit(ImageFit.Cover).borderRadius(20)
          this.FilterPanel()
          Button({ type: ButtonType.Capsule }) {
            Row({ space: 8 }) {
              if (this.loading) { LoadingProgress().width(20).height(20).color('#FFFFFFFF') }
              else { SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(18).fontColor(['#FFFFFFFF']) }
              Text(this.loading ? '正在查询...' : '查询空闲教室').fontColor('#FFFFFFFF').fontSize(15).fontWeight(FontWeight.Bold)
            }
          }.width('100%').height(52).backgroundColor(this.palette().primary).onClick(() => this.onQuery())
          Row() {
            Row({ space: 8 }) {
              Rect().width(5).height(24).fill(this.palette().primary).radius(3)
              Text('推荐空教室').fontColor(this.palette().text).fontSize(17).fontWeight(FontWeight.Bold)
            }
            Blank()
            Text(`共 ${this.classrooms.length} 间可用`).fontColor(this.palette().muted).fontSize(10)
          }.width('100%').alignItems(VerticalAlign.Center)
          if (!this.loading && this.classrooms.length === 0) {
            Text('当前条件下没有可用教室，请调整筛选条件。').fontColor(this.palette().muted).fontSize(12).padding({ top: 24, bottom: 28 })
          } else {
            ForEach(this.classrooms, (item: ClassroomAvailability) => { this.ClassroomCard(item) })
          }
        }.width('100%').padding({ left: 14, right: 14, bottom: 24 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

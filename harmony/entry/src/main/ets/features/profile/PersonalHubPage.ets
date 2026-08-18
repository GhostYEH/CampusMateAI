import { FavoriteItem, PersonalFileItem } from '../../data/Models';
import { CampusPalette, darkPalette, lightPalette } from '../../ui/Theme';
import { SecondaryHeader } from '../../ui/SecondaryHeader';
import { MotionDuration, MotionSpec } from '../../ui/MotionSpec';

@Component
export struct PersonalHubPage {
  @Prop section: string = 'files';
  @Prop files: PersonalFileItem[] = [];
  @Prop favorites: FavoriteItem[] = [];
  @Prop loading: boolean = false;
  @Prop darkMode: boolean = false;
  @Prop reduceMotion: boolean = false;
  @State query: string = '';
  onBack: () => void = () => {};
  onRefresh: () => void = () => {};
  palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
  title(): string { return this.section === 'files' ? '文件' : '收藏'; }

  @Builder FileRow(item: PersonalFileItem) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.doc_text')).fontSize(21).fontColor([this.palette().primary]) }
        .width(44).height(44).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 3 }) {
        Text(item.name).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(`${item.category ?? '其他'} · ${item.size_label ?? '未知大小'}`).fontColor(this.palette().muted).fontSize(10)
        Text(`${item.updated_at ?? ''} · ${item.source ?? '当前账号'}`).fontColor(this.palette().muted).fontSize(9).maxLines(1)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      if (item.is_favorite === true) {
        SymbolGlyph($r('sys.symbol.bookmark_fill')).fontSize(18).fontColor([this.palette().primary])
      } else {
        SymbolGlyph($r('sys.symbol.bookmark')).fontSize(18).fontColor([this.palette().primary])
      }
    }.width('100%').padding({ top: 11, bottom: 11 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  @Builder FavoriteRow(item: FavoriteItem) {
    Row({ space: 11 }) {
      Stack({ alignContent: Alignment.Center }) { SymbolGlyph($r('sys.symbol.bookmark_fill')).fontSize(20).fontColor([this.palette().primary]) }
        .width(44).height(44).backgroundColor(this.palette().soft).borderRadius(13)
      Column({ space: 4 }) {
        Text(item.title).fontColor(this.palette().text).fontSize(13).fontWeight(FontWeight.Bold).maxLines(1)
        Text(item.subtitle ?? '已保存到当前账号').fontColor(this.palette().muted).fontSize(10).maxLines(1)
        Text(`${item.type ?? '内容'} · 收藏于 ${item.saved_at ?? ''}`).fontColor(this.palette().muted).fontSize(9)
      }.layoutWeight(1).alignItems(HorizontalAlign.Start)
    }.width('100%').padding({ top: 11, bottom: 11 })
    .transition(TransitionEffect.OPACITY.combine(TransitionEffect.translate({ y: MotionSpec.distance(this.reduceMotion, 14) })).animation({ duration: MotionSpec.fadeDuration(this.reduceMotion, MotionDuration.PAGE), curve: Curve.EaseOut }))
  }

  build() {
    Column() {
      SecondaryHeader({ title: `我的${this.title()}`, subtitle: '内容仅保存在当前登录账号下', darkMode: this.darkMode, reduceMotion: this.reduceMotion, onBack: () => this.onBack() })
      Scroll() {
        Column({ space: 12 }) {
          Row({ space: 8 }) {
            SymbolGlyph($r('sys.symbol.magnifyingglass')).fontSize(17).fontColor([this.palette().muted])
            TextInput({ placeholder: `搜索${this.title()}`, text: this.query }).layoutWeight(1).height(43).backgroundColor(Color.Transparent)
              .fontColor(this.palette().text).placeholderColor(this.palette().muted).onChange((value: string) => this.query = value)
            Text('刷新').fontColor(this.palette().primary).fontSize(11).onClick(() => this.onRefresh())
          }.width('100%').height(50).padding({ left: 12, right: 12 }).backgroundColor(this.palette().surface)
            .border({ width: 1, color: this.palette().line }).borderRadius(16)
          if (this.loading) {
            LoadingProgress().width(34).height(34).color(this.palette().primary).margin({ top: 40 })
          } else if (this.section === 'files') {
            if (this.files.length === 0) { Text('没有找到文件').fontColor(this.palette().muted).fontSize(12).padding(34) }
            else {
              Column() {
                ForEach(this.files, (item: PersonalFileItem, index: number) => { this.FileRow(item); if (index < this.files.length - 1) { Divider().color(this.palette().line) } }, (item: PersonalFileItem) => item.id)
              }.padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
            }
          } else {
            if (this.favorites.length === 0) { Text('还没有收藏').fontColor(this.palette().muted).fontSize(12).padding(34) }
            else {
              Column() {
                ForEach(this.favorites, (item: FavoriteItem, index: number) => { this.FavoriteRow(item); if (index < this.favorites.length - 1) { Divider().color(this.palette().line) } }, (item: FavoriteItem) => item.id)
              }.padding({ left: 13, right: 13 }).backgroundColor(this.palette().surface).borderRadius(18)
            }
          }
          Blank().height(24)
        }.width('100%').padding({ left: 14, right: 14, bottom: 18 })
      }.layoutWeight(1).width('100%').align(Alignment.Top).scrollBar(BarState.Off)
    }.width('100%').height('100%').backgroundColor(this.palette().background)
  }
}

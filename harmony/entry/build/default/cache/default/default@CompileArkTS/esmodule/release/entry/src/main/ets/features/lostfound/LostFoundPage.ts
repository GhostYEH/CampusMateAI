if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface LostFoundPage_Params {
    items?: LostFoundItem[];
    loading?: boolean;
    submitting?: boolean;
    darkMode?: boolean;
    kind?: string;
    query?: string;
    showPublish?: boolean;
    title?: string;
    content?: string;
    location?: string;
    contact?: string;
    onBack?: () => void;
    onFilter?: (kind: string) => void;
    onSubmit?: (kind: string, title: string, content: string, location: string, contact: string) => void;
}
import type { LostFoundItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class LostFoundPage extends ViewPU {
    constructor(s19, t19, u19, v19 = -1, w19 = undefined, x19) {
        super(s19, u19, v19, x19);
        if (typeof w19 === "function") {
            this.paramsGenerator_ = w19;
        }
        this.__items = new SynchedPropertyObjectOneWayPU(t19.items, this, "items");
        this.__loading = new SynchedPropertySimpleOneWayPU(t19.loading, this, "loading");
        this.__submitting = new SynchedPropertySimpleOneWayPU(t19.submitting, this, "submitting");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(t19.darkMode, this, "darkMode");
        this.__kind = new ObservedPropertySimplePU('lost', this, "kind");
        this.__query = new ObservedPropertySimplePU('', this, "query");
        this.__showPublish = new ObservedPropertySimplePU(false, this, "showPublish");
        this.__title = new ObservedPropertySimplePU('', this, "title");
        this.__content = new ObservedPropertySimplePU('', this, "content");
        this.__location = new ObservedPropertySimplePU('', this, "location");
        this.__contact = new ObservedPropertySimplePU('', this, "contact");
        this.onBack = () => { };
        this.onFilter = () => { };
        this.onSubmit = () => { };
        this.setInitiallyProvidedValue(t19);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(r19: LostFoundPage_Params) {
        if (r19.items === undefined) {
            this.__items.set([]);
        }
        if (r19.loading === undefined) {
            this.__loading.set(false);
        }
        if (r19.submitting === undefined) {
            this.__submitting.set(false);
        }
        if (r19.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (r19.kind !== undefined) {
            this.kind = r19.kind;
        }
        if (r19.query !== undefined) {
            this.query = r19.query;
        }
        if (r19.showPublish !== undefined) {
            this.showPublish = r19.showPublish;
        }
        if (r19.title !== undefined) {
            this.title = r19.title;
        }
        if (r19.content !== undefined) {
            this.content = r19.content;
        }
        if (r19.location !== undefined) {
            this.location = r19.location;
        }
        if (r19.contact !== undefined) {
            this.contact = r19.contact;
        }
        if (r19.onBack !== undefined) {
            this.onBack = r19.onBack;
        }
        if (r19.onFilter !== undefined) {
            this.onFilter = r19.onFilter;
        }
        if (r19.onSubmit !== undefined) {
            this.onSubmit = r19.onSubmit;
        }
    }
    updateStateVars(q19: LostFoundPage_Params) {
        this.__items.reset(q19.items);
        this.__loading.reset(q19.loading);
        this.__submitting.reset(q19.submitting);
        this.__darkMode.reset(q19.darkMode);
    }
    purgeVariableDependenciesOnElmtId(p19) {
        this.__items.purgeDependencyOnElmtId(p19);
        this.__loading.purgeDependencyOnElmtId(p19);
        this.__submitting.purgeDependencyOnElmtId(p19);
        this.__darkMode.purgeDependencyOnElmtId(p19);
        this.__kind.purgeDependencyOnElmtId(p19);
        this.__query.purgeDependencyOnElmtId(p19);
        this.__showPublish.purgeDependencyOnElmtId(p19);
        this.__title.purgeDependencyOnElmtId(p19);
        this.__content.purgeDependencyOnElmtId(p19);
        this.__location.purgeDependencyOnElmtId(p19);
        this.__contact.purgeDependencyOnElmtId(p19);
    }
    aboutToBeDeleted() {
        this.__items.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__submitting.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__kind.aboutToBeDeleted();
        this.__query.aboutToBeDeleted();
        this.__showPublish.aboutToBeDeleted();
        this.__title.aboutToBeDeleted();
        this.__content.aboutToBeDeleted();
        this.__location.aboutToBeDeleted();
        this.__contact.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __items: SynchedPropertySimpleOneWayPU<LostFoundItem[]>;
    get items() {
        return this.__items.get();
    }
    set items(o19: LostFoundItem[]) {
        this.__items.set(o19);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(n19: boolean) {
        this.__loading.set(n19);
    }
    private __submitting: SynchedPropertySimpleOneWayPU<boolean>;
    get submitting() {
        return this.__submitting.get();
    }
    set submitting(m19: boolean) {
        this.__submitting.set(m19);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(l19: boolean) {
        this.__darkMode.set(l19);
    }
    private __kind: ObservedPropertySimplePU<string>;
    get kind() {
        return this.__kind.get();
    }
    set kind(k19: string) {
        this.__kind.set(k19);
    }
    private __query: ObservedPropertySimplePU<string>;
    get query() {
        return this.__query.get();
    }
    set query(j19: string) {
        this.__query.set(j19);
    }
    private __showPublish: ObservedPropertySimplePU<boolean>;
    get showPublish() {
        return this.__showPublish.get();
    }
    set showPublish(i19: boolean) {
        this.__showPublish.set(i19);
    }
    private __title: ObservedPropertySimplePU<string>;
    get title() {
        return this.__title.get();
    }
    set title(h19: string) {
        this.__title.set(h19);
    }
    private __content: ObservedPropertySimplePU<string>;
    get content() {
        return this.__content.get();
    }
    set content(g19: string) {
        this.__content.set(g19);
    }
    private __location: ObservedPropertySimplePU<string>;
    get location() {
        return this.__location.get();
    }
    set location(f19: string) {
        this.__location.set(f19);
    }
    private __contact: ObservedPropertySimplePU<string>;
    get contact() {
        return this.__contact.get();
    }
    set contact(e19: string) {
        this.__contact.set(e19);
    }
    private onBack: () => void;
    private onFilter: (kind: string) => void;
    private onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    imageFor(d19: number): Resource {
        if (d19 % 4 === 0)
            return { "id": 16777230, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        if (d19 % 4 === 1)
            return { "id": 16777231, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        if (d19 % 4 === 2)
            return { "id": 16777232, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        return { "id": 16777233, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
    }
    filteredItems(): LostFoundItem[] {
        const b19 = this.query.trim();
        return this.items.filter((c19: LostFoundItem) => c19.kind === this.kind && (b19.length === 0 || c19.title.includes(b19) || (c19.location ?? '').includes(b19)));
    }
    Tabs(n18 = null) {
        this.observeComponentCreation2((z18, a19) => {
            Row.create();
            Row.width('100%');
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((o18, p18) => {
            ForEach.create();
            const q18 = r18 => {
                const s18 = r18;
                this.observeComponentCreation2((x18, y18) => {
                    Column.create({ space: 5 });
                    Column.layoutWeight(1);
                    Column.padding({ top: 8, bottom: 6 });
                    Column.onClick(() => { this.kind = s18[0]; this.onFilter(s18[0]); });
                }, Column);
                this.observeComponentCreation2((v18, w18) => {
                    Text.create(s18[1]);
                    Text.fontColor(this.kind === s18[0] ? this.palette().primary : this.palette().muted);
                    Text.fontSize(14);
                    Text.fontWeight(FontWeight.Bold);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((t18, u18) => {
                    Rect.create();
                    Rect.width(32);
                    Rect.height(3);
                    Rect.fill(this.kind === s18[0] ? this.palette().primary : Color.Transparent);
                    Rect.radius(2);
                }, Rect);
                Column.pop();
            };
            this.forEachUpdateFunction(o18, [['lost', '失物'], ['found', '招领']], q18);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    ItemCard(m17: LostFoundItem, n17: number, o17 = null) {
        this.observeComponentCreation2((l18, m18) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(11);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
            Row.border({ width: 1, color: this.palette().line });
        }, Row);
        this.observeComponentCreation2((j18, k18) => {
            Image.create(this.imageFor(n17));
            Image.width(104);
            Image.height(92);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(14);
        }, Image);
        this.observeComponentCreation2((h18, i18) => {
            Column.create({ space: 6 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((f18, g18) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((d18, e18) => {
            Text.create(m17.kind === 'lost' ? '失物' : '招领');
            Text.fontColor(m17.kind === 'lost' ? '#FFE35F42' : this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
            Text.padding({ left: 7, right: 7, top: 4, bottom: 4 });
            Text.backgroundColor(m17.kind === 'lost' ? '#FFFFEFEA' : '#FFEAF9F3');
            Text.borderRadius(9);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((b18, c18) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((z17, a18) => {
            Text.create(m17.status === 'closed' ? '已解决' : '寻找中');
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((x17, y17) => {
            Text.create(m17.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((v17, w17) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((t17, u17) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((r17, s17) => {
            Text.create(m17.location ?? '地点未填写');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((p17, q17) => {
            Text.create((m17.created_at ?? '').substring(0, Math.min(10, (m17.created_at ?? '').length)));
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    BrowsePage(l15 = null) {
        this.observeComponentCreation2((k17, l17) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((i17, j17) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((g17, h17) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(176);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((e17, f17) => {
            Image.create({ "id": 16777228, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(176);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((c17, d17) => {
            Column.create({ space: 4 });
            Column.padding({ left: 16, bottom: 14 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((a17, b17) => {
            Text.create('失物招领');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(27);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((y16, z16) => {
            Text.create('让每一件物品，都有机会回到主人身边');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.Tabs.bind(this)();
        this.observeComponentCreation2((w16, x16) => {
            Row.create({ space: 9 });
            Row.width('100%');
            Row.height(52);
            Row.padding({ left: 12, right: 7 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(17);
        }, Row);
        this.observeComponentCreation2((u16, v16) => {
            SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((r16, s16) => {
            TextInput.create({ placeholder: '搜索物品、地点', text: this.query });
            TextInput.layoutWeight(1);
            TextInput.height(44);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(Color.Transparent);
            TextInput.onChange((t16: string) => this.query = t16);
        }, TextInput);
        this.observeComponentCreation2((p16, q16) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(38);
            Stack.height(38);
            Stack.backgroundColor(this.palette().primary);
            Stack.borderRadius(19);
            Stack.onClick(() => this.showPublish = true);
        }, Stack);
        this.observeComponentCreation2((n16, o16) => {
            SymbolGlyph.create({ "id": 125831481, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        Row.pop();
        this.observeComponentCreation2((l16, m16) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((j16, k16) => {
            Text.create(this.kind === 'lost' ? '正在寻找' : '最新招领');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h16, i16) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((f16, g16) => {
            Text.create(`${this.filteredItems().length} 条`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((m15, n15) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((d16, e16) => {
                        LoadingProgress.create();
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 32 });
                    }, LoadingProgress);
                });
            }
            else if (this.filteredItems().length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((b16, c16) => {
                        Column.create({ space: 8 });
                        Column.width('100%');
                        Column.padding({ top: 30, bottom: 30 });
                    }, Column);
                    this.observeComponentCreation2((z15, a16) => {
                        SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(32);
                        SymbolGlyph.fontColor([this.palette().muted]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((x15, y15) => {
                        Text.create('没有找到匹配的失物信息');
                        Text.fontColor(this.palette().text);
                        Text.fontSize(14);
                        Text.fontWeight(FontWeight.Medium);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((v15, w15) => {
                        Text.create('换个关键词或筛选条件试试');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(11);
                    }, Text);
                    Text.pop();
                    Column.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((o15, p15) => {
                        ForEach.create();
                        const q15 = (s15, t15: number) => {
                            const u15 = s15;
                            this.ItemCard.bind(this)(u15, t15);
                        };
                        this.forEachUpdateFunction(o15, this.filteredItems(), q15, (r15: LostFoundItem) => r15.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Scroll.pop();
    }
    PublishPage(h14 = null) {
        this.observeComponentCreation2((j15, k15) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((h15, i15) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 17, right: 17, top: 6, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((f15, g15) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((y14, z14) => {
            ForEach.create();
            const a15 = b15 => {
                const c15 = b15;
                this.observeComponentCreation2((d15, e15) => {
                    Text.create(c15[1]);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(11);
                    Text.padding({ top: 9, bottom: 9 });
                    Text.fontColor(this.kind === c15[0] ? '#FFFFFFFF' : this.palette().muted);
                    Text.backgroundColor(this.kind === c15[0] ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.kind === c15[0] ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.kind = c15[0]);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(y14, [['lost', '我丢了物品'], ['found', '我捡到物品']], a15);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((v14, w14) => {
            TextInput.create({ placeholder: '物品名称或信息标题', text: this.title });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((x14: string) => this.title = x14);
        }, TextInput);
        this.observeComponentCreation2((s14, t14) => {
            TextArea.create({ placeholder: '描述物品特征、丢失或拾到的经过', text: this.content });
            TextArea.height(132);
            TextArea.fontColor(this.palette().text);
            TextArea.placeholderColor(this.palette().muted);
            TextArea.backgroundColor(this.palette().surface);
            TextArea.border({ width: 1, color: this.palette().line });
            TextArea.borderRadius(15);
            TextArea.onChange((u14: string) => this.content = u14);
        }, TextArea);
        this.observeComponentCreation2((p14, q14) => {
            TextInput.create({ placeholder: '地点', text: this.location });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((r14: string) => this.location = r14);
        }, TextInput);
        this.observeComponentCreation2((m14, n14) => {
            TextInput.create({ placeholder: '联系方式', text: this.contact });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((o14: string) => this.contact = o14);
        }, TextInput);
        this.observeComponentCreation2((k14, l14) => {
            Button.createWithLabel(this.submitting ? '发布中...' : '发布信息');
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.fontColor('#FFFFFFFF');
            Button.enabled(!this.submitting && this.title.trim().length > 0);
            Button.onClick(() => { this.onSubmit(this.kind, this.title.trim(), this.content.trim(), this.location.trim(), this.contact.trim()); this.showPublish = false; });
        }, Button);
        Button.pop();
        this.observeComponentCreation2((i14, j14) => {
            Button.createWithLabel('返回失物招领');
            Button.width('100%');
            Button.height(46);
            Button.backgroundColor(this.palette().soft);
            Button.fontColor(this.palette().primary);
            Button.onClick(() => this.showPublish = false);
        }, Button);
        Button.pop();
        Column.pop();
        Scroll.pop();
    }
    initialRender() {
        this.observeComponentCreation2((f14, g14) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((b14, c14) => {
                if (c14) {
                    let d14 = new SecondaryHeader(this, { title: this.showPublish ? '发布失物招领' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息', darkMode: this.darkMode, onBack: () => this.showPublish ? this.showPublish = false : this.onBack() }, undefined, b14, () => { }, { page: "entry/src/main/ets/features/lostfound/LostFoundPage.ets", line: 139, col: 7 });
                    ViewPU.create(d14);
                    let e14 = () => {
                        return {
                            title: this.showPublish ? '发布失物招领' : '失物招领',
                            subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息',
                            darkMode: this.darkMode,
                            onBack: () => this.showPublish ? this.showPublish = false : this.onBack()
                        };
                    };
                    d14.paramsGenerator_ = e14;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(b14, {
                        title: this.showPublish ? '发布失物招领' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((z13, a14) => {
            If.create();
            if (this.showPublish) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.PublishPage.bind(this)();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.BrowsePage.bind(this)();
                });
            }
        }, If);
        If.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

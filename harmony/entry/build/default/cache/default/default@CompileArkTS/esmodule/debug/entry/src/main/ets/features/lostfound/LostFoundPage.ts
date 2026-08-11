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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__items = new SynchedPropertyObjectOneWayPU(params.items, this, "items");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__submitting = new SynchedPropertySimpleOneWayPU(params.submitting, this, "submitting");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
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
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: LostFoundPage_Params) {
        if (params.items === undefined) {
            this.__items.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.submitting === undefined) {
            this.__submitting.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.kind !== undefined) {
            this.kind = params.kind;
        }
        if (params.query !== undefined) {
            this.query = params.query;
        }
        if (params.showPublish !== undefined) {
            this.showPublish = params.showPublish;
        }
        if (params.title !== undefined) {
            this.title = params.title;
        }
        if (params.content !== undefined) {
            this.content = params.content;
        }
        if (params.location !== undefined) {
            this.location = params.location;
        }
        if (params.contact !== undefined) {
            this.contact = params.contact;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onFilter !== undefined) {
            this.onFilter = params.onFilter;
        }
        if (params.onSubmit !== undefined) {
            this.onSubmit = params.onSubmit;
        }
    }
    updateStateVars(params: LostFoundPage_Params) {
        this.__items.reset(params.items);
        this.__loading.reset(params.loading);
        this.__submitting.reset(params.submitting);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__items.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__submitting.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__kind.purgeDependencyOnElmtId(rmElmtId);
        this.__query.purgeDependencyOnElmtId(rmElmtId);
        this.__showPublish.purgeDependencyOnElmtId(rmElmtId);
        this.__title.purgeDependencyOnElmtId(rmElmtId);
        this.__content.purgeDependencyOnElmtId(rmElmtId);
        this.__location.purgeDependencyOnElmtId(rmElmtId);
        this.__contact.purgeDependencyOnElmtId(rmElmtId);
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
    set items(newValue: LostFoundItem[]) {
        this.__items.set(newValue);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(newValue: boolean) {
        this.__loading.set(newValue);
    }
    private __submitting: SynchedPropertySimpleOneWayPU<boolean>;
    get submitting() {
        return this.__submitting.get();
    }
    set submitting(newValue: boolean) {
        this.__submitting.set(newValue);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __kind: ObservedPropertySimplePU<string>;
    get kind() {
        return this.__kind.get();
    }
    set kind(newValue: string) {
        this.__kind.set(newValue);
    }
    private __query: ObservedPropertySimplePU<string>;
    get query() {
        return this.__query.get();
    }
    set query(newValue: string) {
        this.__query.set(newValue);
    }
    private __showPublish: ObservedPropertySimplePU<boolean>;
    get showPublish() {
        return this.__showPublish.get();
    }
    set showPublish(newValue: boolean) {
        this.__showPublish.set(newValue);
    }
    private __title: ObservedPropertySimplePU<string>;
    get title() {
        return this.__title.get();
    }
    set title(newValue: string) {
        this.__title.set(newValue);
    }
    private __content: ObservedPropertySimplePU<string>;
    get content() {
        return this.__content.get();
    }
    set content(newValue: string) {
        this.__content.set(newValue);
    }
    private __location: ObservedPropertySimplePU<string>;
    get location() {
        return this.__location.get();
    }
    set location(newValue: string) {
        this.__location.set(newValue);
    }
    private __contact: ObservedPropertySimplePU<string>;
    get contact() {
        return this.__contact.get();
    }
    set contact(newValue: string) {
        this.__contact.set(newValue);
    }
    private onBack: () => void;
    private onFilter: (kind: string) => void;
    private onSubmit: (kind: string, title: string, content: string, location: string, contact: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    imageFor(index: number): Resource {
        if (index % 4 === 0)
            return { "id": 16777230, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        if (index % 4 === 1)
            return { "id": 16777231, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        if (index % 4 === 2)
            return { "id": 16777232, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
        return { "id": 16777233, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" };
    }
    filteredItems(): LostFoundItem[] {
        const key = this.query.trim();
        return this.items.filter((item: LostFoundItem) => item.kind === this.kind && (key.length === 0 || item.title.includes(key) || (item.location ?? '').includes(key)));
    }
    Tabs(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const entry = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Column.create({ space: 5 });
                    Column.layoutWeight(1);
                    Column.padding({ top: 8, bottom: 6 });
                    Column.onClick(() => { this.kind = entry[0]; this.onFilter(entry[0]); });
                }, Column);
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(entry[1]);
                    Text.fontColor(this.kind === entry[0] ? this.palette().primary : this.palette().muted);
                    Text.fontSize(14);
                    Text.fontWeight(FontWeight.Bold);
                }, Text);
                Text.pop();
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Rect.create();
                    Rect.width(32);
                    Rect.height(3);
                    Rect.fill(this.kind === entry[0] ? this.palette().primary : Color.Transparent);
                    Rect.radius(2);
                }, Rect);
                Column.pop();
            };
            this.forEachUpdateFunction(elmtId, [['lost', '失物'], ['found', '招领']], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    ItemCard(item: LostFoundItem, index: number, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(11);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
            Row.border({ width: 1, color: this.palette().line });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create(this.imageFor(index));
            Image.width(104);
            Image.height(92);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(14);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 6 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.kind === 'lost' ? '失物' : '招领');
            Text.fontColor(item.kind === 'lost' ? '#FFE35F42' : this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
            Text.padding({ left: 7, right: 7, top: 4, bottom: 4 });
            Text.backgroundColor(item.kind === 'lost' ? '#FFFFEFEA' : '#FFEAF9F3');
            Text.borderRadius(9);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.status === 'closed' ? '已解决' : '寻找中');
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.location ?? '地点未填写');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create((item.created_at ?? '').substring(0, Math.min(10, (item.created_at ?? '').length)));
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    BrowsePage(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(176);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777228, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(176);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 4 });
            Column.padding({ left: 16, bottom: 14 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('失物招领');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(27);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('让每一件物品，都有机会回到主人身边');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.Tabs.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 9 });
            Row.width('100%');
            Row.height(52);
            Row.padding({ left: 12, right: 7 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(17);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: '搜索物品、地点', text: this.query });
            TextInput.layoutWeight(1);
            TextInput.height(44);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(Color.Transparent);
            TextInput.onChange((value: string) => this.query = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(38);
            Stack.height(38);
            Stack.backgroundColor(this.palette().primary);
            Stack.borderRadius(19);
            Stack.onClick(() => this.showPublish = true);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831481, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.kind === 'lost' ? '正在寻找' : '最新招领');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${this.filteredItems().length} 条`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Column.create({ space: 8 });
                        Column.width('100%');
                        Column.padding({ top: 30, bottom: 30 });
                    }, Column);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(32);
                        SymbolGlyph.fontColor([this.palette().muted]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('没有找到匹配的失物信息');
                        Text.fontColor(this.palette().text);
                        Text.fontSize(14);
                        Text.fontWeight(FontWeight.Medium);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = (_item, index: number) => {
                            const item = _item;
                            this.ItemCard.bind(this)(item, index);
                        };
                        this.forEachUpdateFunction(elmtId, this.filteredItems(), forEachItemGenFunction, (item: LostFoundItem) => item.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Scroll.pop();
    }
    PublishPage(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 17, right: 17, top: 6, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const entry = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(entry[1]);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(11);
                    Text.padding({ top: 9, bottom: 9 });
                    Text.fontColor(this.kind === entry[0] ? '#FFFFFFFF' : this.palette().muted);
                    Text.backgroundColor(this.kind === entry[0] ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.kind === entry[0] ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.kind = entry[0]);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(elmtId, [['lost', '我丢了物品'], ['found', '我捡到物品']], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: '物品名称或信息标题', text: this.title });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((value: string) => this.title = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextArea.create({ placeholder: '描述物品特征、丢失或拾到的经过', text: this.content });
            TextArea.height(132);
            TextArea.fontColor(this.palette().text);
            TextArea.placeholderColor(this.palette().muted);
            TextArea.backgroundColor(this.palette().surface);
            TextArea.border({ width: 1, color: this.palette().line });
            TextArea.borderRadius(15);
            TextArea.onChange((value: string) => this.content = value);
        }, TextArea);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: '地点', text: this.location });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((value: string) => this.location = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: '联系方式', text: this.contact });
            TextInput.height(50);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((value: string) => this.contact = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel(this.submitting ? '发布中...' : '发布信息');
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.fontColor('#FFFFFFFF');
            Button.enabled(!this.submitting && this.title.trim().length > 0);
            Button.onClick(() => { this.onSubmit(this.kind, this.title.trim(), this.content.trim(), this.location.trim(), this.contact.trim()); this.showPublish = false; });
        }, Button);
        Button.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: this.showPublish ? '发布失物招领' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息', darkMode: this.darkMode, onBack: () => this.showPublish ? this.showPublish = false : this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/lostfound/LostFoundPage.ets", line: 139, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: this.showPublish ? '发布失物招领' : '失物招领',
                            subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息',
                            darkMode: this.darkMode,
                            onBack: () => this.showPublish ? this.showPublish = false : this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: this.showPublish ? '发布失物招领' : '失物招领', subtitle: this.showPublish ? '请如实填写物品信息' : '搜索、筛选并发布真实信息', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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

if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface ServicesPage_Params {
    requests?: ServiceRequestItem[];
    loading?: boolean;
    submitting?: boolean;
    darkMode?: boolean;
    showForm?: boolean;
    formKind?: string;
    formTitle?: string;
    formContent?: string;
    selectedId?: string;
    onBack?: () => void;
    onRefresh?: () => void;
    onSubmit?: (kind: string, title: string, content: string) => void;
}
import type { ServiceRequestItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class ServicesPage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__requests = new SynchedPropertyObjectOneWayPU(params.requests, this, "requests");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__submitting = new SynchedPropertySimpleOneWayPU(params.submitting, this, "submitting");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__showForm = new ObservedPropertySimplePU(false, this, "showForm");
        this.__formKind = new ObservedPropertySimplePU('leave', this, "formKind");
        this.__formTitle = new ObservedPropertySimplePU('', this, "formTitle");
        this.__formContent = new ObservedPropertySimplePU('', this, "formContent");
        this.__selectedId = new ObservedPropertySimplePU('', this, "selectedId");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.onSubmit = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: ServicesPage_Params) {
        if (params.requests === undefined) {
            this.__requests.set([]);
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
        if (params.showForm !== undefined) {
            this.showForm = params.showForm;
        }
        if (params.formKind !== undefined) {
            this.formKind = params.formKind;
        }
        if (params.formTitle !== undefined) {
            this.formTitle = params.formTitle;
        }
        if (params.formContent !== undefined) {
            this.formContent = params.formContent;
        }
        if (params.selectedId !== undefined) {
            this.selectedId = params.selectedId;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onRefresh !== undefined) {
            this.onRefresh = params.onRefresh;
        }
        if (params.onSubmit !== undefined) {
            this.onSubmit = params.onSubmit;
        }
    }
    updateStateVars(params: ServicesPage_Params) {
        this.__requests.reset(params.requests);
        this.__loading.reset(params.loading);
        this.__submitting.reset(params.submitting);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__requests.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__submitting.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__showForm.purgeDependencyOnElmtId(rmElmtId);
        this.__formKind.purgeDependencyOnElmtId(rmElmtId);
        this.__formTitle.purgeDependencyOnElmtId(rmElmtId);
        this.__formContent.purgeDependencyOnElmtId(rmElmtId);
        this.__selectedId.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__requests.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__submitting.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__showForm.aboutToBeDeleted();
        this.__formKind.aboutToBeDeleted();
        this.__formTitle.aboutToBeDeleted();
        this.__formContent.aboutToBeDeleted();
        this.__selectedId.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __requests: SynchedPropertySimpleOneWayPU<ServiceRequestItem[]>;
    get requests() {
        return this.__requests.get();
    }
    set requests(newValue: ServiceRequestItem[]) {
        this.__requests.set(newValue);
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
    private __showForm: ObservedPropertySimplePU<boolean>;
    get showForm() {
        return this.__showForm.get();
    }
    set showForm(newValue: boolean) {
        this.__showForm.set(newValue);
    }
    private __formKind: ObservedPropertySimplePU<string>;
    get formKind() {
        return this.__formKind.get();
    }
    set formKind(newValue: string) {
        this.__formKind.set(newValue);
    }
    private __formTitle: ObservedPropertySimplePU<string>;
    get formTitle() {
        return this.__formTitle.get();
    }
    set formTitle(newValue: string) {
        this.__formTitle.set(newValue);
    }
    private __formContent: ObservedPropertySimplePU<string>;
    get formContent() {
        return this.__formContent.get();
    }
    set formContent(newValue: string) {
        this.__formContent.set(newValue);
    }
    private __selectedId: ObservedPropertySimplePU<string>;
    get selectedId() {
        return this.__selectedId.get();
    }
    set selectedId(newValue: string) {
        this.__selectedId.set(newValue);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    private onSubmit: (kind: string, title: string, content: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    selectedRequest(): ServiceRequestItem | undefined { return this.requests.find((item: ServiceRequestItem) => item.id === this.selectedId); }
    kindTitle(kind: string): string {
        if (kind === 'leave')
            return '请假申请';
        if (kind === 'repair')
            return '宿舍报修';
        if (kind === 'certificate')
            return '证明开具';
        return '意见反馈';
    }
    openForm(kind: string): void {
        this.formKind = kind;
        this.formTitle = '';
        this.formContent = '';
        this.showForm = true;
    }
    ServiceTile(kind: string, subtitle: string, symbol: Resource, color: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 8 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(37:5)", "entry");
            Column.width('48%');
            Column.padding({ top: 15, bottom: 15 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
            Column.onClick(() => this.openForm(kind));
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(38:7)", "entry");
            Stack.width(46);
            Stack.height(46);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(39:9)", "entry");
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor([color]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.kindTitle(kind));
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(41:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(subtitle);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(42:7)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
    }
    RequestRow(item: ServiceRequestItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 10 });
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(48:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
            Row.onClick(() => this.selectedId = item.id);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(49:7)", "entry");
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (item.kind === 'repair') {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125832927, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(51:11)", "entry");
                        SymbolGlyph.fontSize(19);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(53:11)", "entry");
                        SymbolGlyph.fontSize(19);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 4 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(56:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(57:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`申请时间：${item.created_at.substring(0, Math.min(10, item.created_at.length))}`);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(58:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.status === 'completed' ? '已完成' : item.status === 'processing' ? '处理中' : '已提交');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(60:7)", "entry");
            Text.fontColor(item.status === 'completed' ? this.palette().success : this.palette().primary);
            Text.fontSize(10);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(62:7)", "entry");
            SymbolGlyph.fontSize(16);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    DetailPage(item: ServiceRequestItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(67:5)", "entry");
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 14 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(68:7)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 8 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(69:9)", "entry");
            Column.width('100%');
            Column.padding({ top: 22, bottom: 20 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(70:11)", "entry");
            Stack.width(62);
            Stack.height(62);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(20);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(70:55)", "entry");
            SymbolGlyph.fontSize(29);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(72:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(21);
            Text.fontWeight(FontWeight.Bold);
            Text.textAlign(TextAlign.Center);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.status === 'completed' ? '已完成' : item.status === 'processing' ? '处理中' : '已提交');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(73:11)", "entry");
            Text.fontColor(item.status === 'completed' ? this.palette().success : this.palette().primary);
            Text.fontSize(11);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.content ?? '暂无详细说明');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(76:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.lineHeight(21);
            Text.width('100%');
            Text.padding(15);
            Text.backgroundColor(this.palette().surface);
            Text.borderRadius(17);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(77:9)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(17);
        }, Column);
        this.RequestMeta.bind(this)('业务类型', this.kindTitle(item.kind));
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(79:11)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.RequestMeta.bind(this)('申请时间', item.created_at);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(81:11)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.RequestMeta.bind(this)('申请编号', item.id);
        Column.pop();
        Column.pop();
        Scroll.pop();
    }
    RequestMeta(label: string, value: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(89:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 14, bottom: 14 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(89:13)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(89:71)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(value);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(89:80)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
    }
    MainPage(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(94:5)", "entry");
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(95:7)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(96:9)", "entry");
            Stack.width('100%');
            Stack.height(178);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create($r('app.media.hero_services'));
            Image.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(97:11)", "entry");
            Image.width('100%');
            Image.height(178);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 5 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(98:11)", "entry");
            Column.padding({ left: 16, bottom: 15 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('办事大厅');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(99:13)", "entry");
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(28);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('一站式校园服务中心，办事更轻松');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(100:13)", "entry");
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(103:9)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(104:11)", "entry");
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('高频服务 · 一键直达');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(105:13)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('快速处理常用事务，节省您的时间');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(106:13)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(108:11)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${this.requests.length} 条记录`);
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(109:11)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 9 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(111:9)", "entry");
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(112:11)", "entry");
            Row.width('100%');
        }, Row);
        this.ServiceTile.bind(this)('leave', '在线填写请假信息', { "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, this.palette().primary);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(114:13)", "entry");
        }, Blank);
        Blank.pop();
        this.ServiceTile.bind(this)('repair', '提交设施维修申请', { "id": 125832927, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FFF18C5C');
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(117:11)", "entry");
            Row.width('100%');
        }, Row);
        this.ServiceTile.bind(this)('certificate', '常用材料在线申请', { "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FF4E8C6A');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(119:13)", "entry");
        }, Blank);
        Blank.pop();
        this.ServiceTile.bind(this)('feedback', '意见建议直达校园', { "id": 125831766, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FF7A68D8');
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(123:9)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Rect.create();
            Rect.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(124:11)", "entry");
            Rect.width(5);
            Rect.height(24);
            Rect.fill(this.palette().primary);
            Rect.radius(3);
        }, Rect);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('最近申请');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(125:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(126:11)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('刷新');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(127:11)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(129:9)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(131:13)", "entry");
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin(30);
                    }, LoadingProgress);
                });
            }
            else if (this.requests.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('暂无申请记录');
                        Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(133:13)", "entry");
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding(30);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = (_item, index: number) => {
                            const item = _item;
                            this.RequestRow.bind(this)(item);
                            this.observeComponentCreation2((elmtId, isInitialRender) => {
                                If.create();
                                if (index < this.requests.length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                                            Divider.create();
                                            Divider.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(137:55)", "entry");
                                            Divider.color(this.palette().line);
                                        }, Divider);
                                    });
                                }
                                else {
                                    this.ifElseBranchUpdateFunction(1, () => {
                                    });
                                }
                            }, If);
                            If.pop();
                        };
                        this.forEachUpdateFunction(elmtId, this.requests, forEachItemGenFunction, (item: ServiceRequestItem) => item.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Column.pop();
        Scroll.pop();
    }
    FormPage(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 15 });
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(146:5)", "entry");
            Column.width('100%');
            Column.padding({ left: 18, right: 18, top: 12 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.kindTitle(this.formKind));
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(147:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(22);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('填写申请信息，提交后可在最近申请中查看进度。');
            Text.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(148:7)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: '请输入申请标题', text: this.formTitle });
            TextInput.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(149:7)", "entry");
            TextInput.height(52);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((value: string) => this.formTitle = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextArea.create({ placeholder: '请详细说明你的需求', text: this.formContent });
            TextArea.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(152:7)", "entry");
            TextArea.height(160);
            TextArea.fontColor(this.palette().text);
            TextArea.placeholderColor(this.palette().muted);
            TextArea.backgroundColor(this.palette().surface);
            TextArea.border({ width: 1, color: this.palette().line });
            TextArea.borderRadius(15);
            TextArea.onChange((value: string) => this.formContent = value);
        }, TextArea);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel(this.submitting ? '提交中...' : '提交申请');
            Button.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(155:7)", "entry");
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.fontColor('#FFFFFFFF');
            Button.enabled(!this.submitting && this.formTitle.trim().length > 0);
            Button.onClick(() => { this.onSubmit(this.formKind, this.formTitle.trim(), this.formContent.trim()); this.showForm = false; });
        }, Button);
        Button.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel('返回服务大厅');
            Button.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(158:7)", "entry");
            Button.width('100%');
            Button.height(46);
            Button.backgroundColor(this.palette().soft);
            Button.fontColor(this.palette().primary);
            Button.onClick(() => this.showForm = false);
        }, Button);
        Button.pop();
        Column.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/services/ServicesPage.ets(163:5)", "entry");
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: this.showForm ? this.kindTitle(this.formKind) : this.selectedId.length > 0 ? '申请详情' : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : this.selectedId.length > 0 ? '查看校园事务处理进度' : '一站式校园服务中心', darkMode: this.darkMode, onBack: () => this.showForm ? this.showForm = false : this.selectedId.length > 0 ? this.selectedId = '' : this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/services/ServicesPage.ets", line: 164, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: this.showForm ? this.kindTitle(this.formKind) : this.selectedId.length > 0 ? '申请详情' : '办事大厅',
                            subtitle: this.showForm ? '在线提交校园事务' : this.selectedId.length > 0 ? '查看校园事务处理进度' : '一站式校园服务中心',
                            darkMode: this.darkMode,
                            onBack: () => this.showForm ? this.showForm = false : this.selectedId.length > 0 ? this.selectedId = '' : this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: this.showForm ? this.kindTitle(this.formKind) : this.selectedId.length > 0 ? '申请详情' : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : this.selectedId.length > 0 ? '查看校园事务处理进度' : '一站式校园服务中心', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.showForm) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.FormPage.bind(this)();
                });
            }
            else if (this.selectedRequest() !== undefined) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.DetailPage.bind(this)(this.selectedRequest()!);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.MainPage.bind(this)();
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

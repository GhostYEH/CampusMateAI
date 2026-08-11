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
    onBack?: () => void;
    onRefresh?: () => void;
    onSubmit?: (kind: string, title: string, content: string) => void;
}
import type { ServiceRequestItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class ServicesPage extends ViewPU {
    constructor(j25, k25, l25, m25 = -1, n25 = undefined, o25) {
        super(j25, l25, m25, o25);
        if (typeof n25 === "function") {
            this.paramsGenerator_ = n25;
        }
        this.__requests = new SynchedPropertyObjectOneWayPU(k25.requests, this, "requests");
        this.__loading = new SynchedPropertySimpleOneWayPU(k25.loading, this, "loading");
        this.__submitting = new SynchedPropertySimpleOneWayPU(k25.submitting, this, "submitting");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(k25.darkMode, this, "darkMode");
        this.__showForm = new ObservedPropertySimplePU(false, this, "showForm");
        this.__formKind = new ObservedPropertySimplePU('leave', this, "formKind");
        this.__formTitle = new ObservedPropertySimplePU('', this, "formTitle");
        this.__formContent = new ObservedPropertySimplePU('', this, "formContent");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.onSubmit = () => { };
        this.setInitiallyProvidedValue(k25);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(i25: ServicesPage_Params) {
        if (i25.requests === undefined) {
            this.__requests.set([]);
        }
        if (i25.loading === undefined) {
            this.__loading.set(false);
        }
        if (i25.submitting === undefined) {
            this.__submitting.set(false);
        }
        if (i25.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (i25.showForm !== undefined) {
            this.showForm = i25.showForm;
        }
        if (i25.formKind !== undefined) {
            this.formKind = i25.formKind;
        }
        if (i25.formTitle !== undefined) {
            this.formTitle = i25.formTitle;
        }
        if (i25.formContent !== undefined) {
            this.formContent = i25.formContent;
        }
        if (i25.onBack !== undefined) {
            this.onBack = i25.onBack;
        }
        if (i25.onRefresh !== undefined) {
            this.onRefresh = i25.onRefresh;
        }
        if (i25.onSubmit !== undefined) {
            this.onSubmit = i25.onSubmit;
        }
    }
    updateStateVars(h25: ServicesPage_Params) {
        this.__requests.reset(h25.requests);
        this.__loading.reset(h25.loading);
        this.__submitting.reset(h25.submitting);
        this.__darkMode.reset(h25.darkMode);
    }
    purgeVariableDependenciesOnElmtId(g25) {
        this.__requests.purgeDependencyOnElmtId(g25);
        this.__loading.purgeDependencyOnElmtId(g25);
        this.__submitting.purgeDependencyOnElmtId(g25);
        this.__darkMode.purgeDependencyOnElmtId(g25);
        this.__showForm.purgeDependencyOnElmtId(g25);
        this.__formKind.purgeDependencyOnElmtId(g25);
        this.__formTitle.purgeDependencyOnElmtId(g25);
        this.__formContent.purgeDependencyOnElmtId(g25);
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
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __requests: SynchedPropertySimpleOneWayPU<ServiceRequestItem[]>;
    get requests() {
        return this.__requests.get();
    }
    set requests(f25: ServiceRequestItem[]) {
        this.__requests.set(f25);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(e25: boolean) {
        this.__loading.set(e25);
    }
    private __submitting: SynchedPropertySimpleOneWayPU<boolean>;
    get submitting() {
        return this.__submitting.get();
    }
    set submitting(d25: boolean) {
        this.__submitting.set(d25);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(c25: boolean) {
        this.__darkMode.set(c25);
    }
    private __showForm: ObservedPropertySimplePU<boolean>;
    get showForm() {
        return this.__showForm.get();
    }
    set showForm(b25: boolean) {
        this.__showForm.set(b25);
    }
    private __formKind: ObservedPropertySimplePU<string>;
    get formKind() {
        return this.__formKind.get();
    }
    set formKind(a25: string) {
        this.__formKind.set(a25);
    }
    private __formTitle: ObservedPropertySimplePU<string>;
    get formTitle() {
        return this.__formTitle.get();
    }
    set formTitle(z24: string) {
        this.__formTitle.set(z24);
    }
    private __formContent: ObservedPropertySimplePU<string>;
    get formContent() {
        return this.__formContent.get();
    }
    set formContent(y24: string) {
        this.__formContent.set(y24);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    private onSubmit: (kind: string, title: string, content: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    kindTitle(x24: string): string {
        if (x24 === 'leave')
            return '请假申请';
        if (x24 === 'repair')
            return '宿舍报修';
        if (x24 === 'certificate')
            return '证明开具';
        return '意见反馈';
    }
    openForm(w24: string): void {
        this.formKind = w24;
        this.formTitle = '';
        this.formContent = '';
        this.showForm = true;
    }
    ServiceTile(h24: string, i24: string, j24: Resource, k24: string, l24 = null) {
        this.observeComponentCreation2((u24, v24) => {
            Column.create({ space: 8 });
            Column.width('48%');
            Column.padding({ top: 15, bottom: 15 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
            Column.onClick(() => this.openForm(h24));
        }, Column);
        this.observeComponentCreation2((s24, t24) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(46);
            Stack.height(46);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((q24, r24) => {
            SymbolGlyph.create(j24);
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor([k24]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((o24, p24) => {
            Text.create(this.kindTitle(h24));
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((m24, n24) => {
            Text.create(i24);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
    }
    RequestRow(l23: ServiceRequestItem, m23 = null) {
        this.observeComponentCreation2((f24, g24) => {
            Row.create({ space: 10 });
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((d24, e24) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((x23, y23) => {
            If.create();
            if (l23.kind === 'repair') {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((b24, c24) => {
                        SymbolGlyph.create({ "id": 125832927, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(19);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((z23, a24) => {
                        SymbolGlyph.create({ "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(19);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Stack.pop();
        this.observeComponentCreation2((v23, w23) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((t23, u23) => {
            Text.create(l23.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r23, s23) => {
            Text.create(`申请时间：${l23.created_at.substring(0, Math.min(10, l23.created_at.length))}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((p23, q23) => {
            Text.create(l23.status === 'completed' ? '已完成' : l23.status === 'processing' ? '处理中' : '已提交');
            Text.fontColor(l23.status === 'completed' ? this.palette().success : this.palette().primary);
            Text.fontSize(10);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((n23, o23) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(16);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    MainPage(x20 = null) {
        this.observeComponentCreation2((j23, k23) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((h23, i23) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((f23, g23) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(178);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((d23, e23) => {
            Image.create({ "id": 16777229, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(178);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((b23, c23) => {
            Column.create({ space: 5 });
            Column.padding({ left: 16, bottom: 15 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((z22, a23) => {
            Text.create('办事大厅');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(28);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((x22, y22) => {
            Text.create('一站式校园服务中心，办事更轻松');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.observeComponentCreation2((v22, w22) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((t22, u22) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((r22, s22) => {
            Text.create('高频服务 · 一键直达');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((p22, q22) => {
            Text.create('快速处理常用事务，节省您的时间');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((n22, o22) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((l22, m22) => {
            Text.create(`${this.requests.length} 条记录`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((j22, k22) => {
            Column.create({ space: 9 });
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((h22, i22) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.ServiceTile.bind(this)('leave', '在线填写请假信息', { "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, this.palette().primary);
        this.observeComponentCreation2((f22, g22) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.ServiceTile.bind(this)('repair', '提交设施维修申请', { "id": 125832927, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FFF18C5C');
        Row.pop();
        this.observeComponentCreation2((d22, e22) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.ServiceTile.bind(this)('certificate', '常用材料在线申请', { "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FF4E8C6A');
        this.observeComponentCreation2((b22, c22) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.ServiceTile.bind(this)('feedback', '意见建议直达校园', { "id": 125831766, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '#FF7A68D8');
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((z21, a22) => {
            Row.create({ space: 8 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((x21, y21) => {
            Rect.create();
            Rect.width(5);
            Rect.height(24);
            Rect.fill(this.palette().primary);
            Rect.radius(3);
        }, Rect);
        this.observeComponentCreation2((v21, w21) => {
            Text.create('最近申请');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t21, u21) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((r21, s21) => {
            Text.create('刷新');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((p21, q21) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 14, right: 14 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
        }, Column);
        this.observeComponentCreation2((y20, z20) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((n21, o21) => {
                        LoadingProgress.create();
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin(30);
                    }, LoadingProgress);
                });
            }
            else if (this.requests.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((l21, m21) => {
                        Text.create('暂无申请记录');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding(30);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((a21, b21) => {
                        ForEach.create();
                        const c21 = (e21, f21: number) => {
                            const g21 = e21;
                            this.RequestRow.bind(this)(g21);
                            this.observeComponentCreation2((h21, i21) => {
                                If.create();
                                if (f21 < this.requests.length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((j21, k21) => {
                                            Divider.create();
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
                        this.forEachUpdateFunction(a21, this.requests, c21, (d21: ServiceRequestItem) => d21.id, true, false);
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
    FormPage(g20 = null) {
        this.observeComponentCreation2((v20, w20) => {
            Column.create({ space: 15 });
            Column.width('100%');
            Column.padding({ left: 18, right: 18, top: 12 });
        }, Column);
        this.observeComponentCreation2((t20, u20) => {
            Text.create(this.kindTitle(this.formKind));
            Text.fontColor(this.palette().text);
            Text.fontSize(22);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r20, s20) => {
            Text.create('填写申请信息，提交后可在最近申请中查看进度。');
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((o20, p20) => {
            TextInput.create({ placeholder: '请输入申请标题', text: this.formTitle });
            TextInput.height(52);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(15);
            TextInput.onChange((q20: string) => this.formTitle = q20);
        }, TextInput);
        this.observeComponentCreation2((l20, m20) => {
            TextArea.create({ placeholder: '请详细说明你的需求', text: this.formContent });
            TextArea.height(160);
            TextArea.fontColor(this.palette().text);
            TextArea.placeholderColor(this.palette().muted);
            TextArea.backgroundColor(this.palette().surface);
            TextArea.border({ width: 1, color: this.palette().line });
            TextArea.borderRadius(15);
            TextArea.onChange((n20: string) => this.formContent = n20);
        }, TextArea);
        this.observeComponentCreation2((j20, k20) => {
            Button.createWithLabel(this.submitting ? '提交中...' : '提交申请');
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.fontColor('#FFFFFFFF');
            Button.enabled(!this.submitting && this.formTitle.trim().length > 0);
            Button.onClick(() => { this.onSubmit(this.formKind, this.formTitle.trim(), this.formContent.trim()); this.showForm = false; });
        }, Button);
        Button.pop();
        this.observeComponentCreation2((h20, i20) => {
            Button.createWithLabel('返回服务大厅');
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
        this.observeComponentCreation2((e20, f20) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((a20, b20) => {
                if (b20) {
                    let c20 = new SecondaryHeader(this, { title: this.showForm ? this.kindTitle(this.formKind) : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : '一站式校园服务中心', darkMode: this.darkMode, onBack: () => this.showForm ? this.showForm = false : this.onBack() }, undefined, a20, () => { }, { page: "entry/src/main/ets/features/services/ServicesPage.ets", line: 135, col: 7 });
                    ViewPU.create(c20);
                    let d20 = () => {
                        return {
                            title: this.showForm ? this.kindTitle(this.formKind) : '办事大厅',
                            subtitle: this.showForm ? '在线提交校园事务' : '一站式校园服务中心',
                            darkMode: this.darkMode,
                            onBack: () => this.showForm ? this.showForm = false : this.onBack()
                        };
                    };
                    c20.paramsGenerator_ = d20;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(a20, {
                        title: this.showForm ? this.kindTitle(this.formKind) : '办事大厅', subtitle: this.showForm ? '在线提交校园事务' : '一站式校园服务中心', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((y19, z19) => {
            If.create();
            if (this.showForm) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.FormPage.bind(this)();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
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

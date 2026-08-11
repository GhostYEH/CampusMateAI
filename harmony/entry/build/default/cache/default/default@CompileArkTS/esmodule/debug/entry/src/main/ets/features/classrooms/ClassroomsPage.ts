if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface ClassroomsPage_Params {
    classrooms?: ClassroomAvailability[];
    loading?: boolean;
    darkMode?: boolean;
    slot?: string;
    capacity?: string;
    multimedia?: boolean;
    onBack?: () => void;
    onQuery?: () => void;
}
import type { ClassroomAvailability } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class ClassroomsPage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__classrooms = new SynchedPropertyObjectOneWayPU(params.classrooms, this, "classrooms");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__slot = new ObservedPropertySimplePU('1-2节', this, "slot");
        this.__capacity = new ObservedPropertySimplePU('全部容量', this, "capacity");
        this.__multimedia = new ObservedPropertySimplePU(true, this, "multimedia");
        this.onBack = () => { };
        this.onQuery = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: ClassroomsPage_Params) {
        if (params.classrooms === undefined) {
            this.__classrooms.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.slot !== undefined) {
            this.slot = params.slot;
        }
        if (params.capacity !== undefined) {
            this.capacity = params.capacity;
        }
        if (params.multimedia !== undefined) {
            this.multimedia = params.multimedia;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onQuery !== undefined) {
            this.onQuery = params.onQuery;
        }
    }
    updateStateVars(params: ClassroomsPage_Params) {
        this.__classrooms.reset(params.classrooms);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__classrooms.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__slot.purgeDependencyOnElmtId(rmElmtId);
        this.__capacity.purgeDependencyOnElmtId(rmElmtId);
        this.__multimedia.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__classrooms.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__slot.aboutToBeDeleted();
        this.__capacity.aboutToBeDeleted();
        this.__multimedia.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __classrooms: SynchedPropertySimpleOneWayPU<ClassroomAvailability[]>;
    get classrooms() {
        return this.__classrooms.get();
    }
    set classrooms(newValue: ClassroomAvailability[]) {
        this.__classrooms.set(newValue);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(newValue: boolean) {
        this.__loading.set(newValue);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __slot: ObservedPropertySimplePU<string>;
    get slot() {
        return this.__slot.get();
    }
    set slot(newValue: string) {
        this.__slot.set(newValue);
    }
    private __capacity: ObservedPropertySimplePU<string>;
    get capacity() {
        return this.__capacity.get();
    }
    set capacity(newValue: string) {
        this.__capacity.set(newValue);
    }
    private __multimedia: ObservedPropertySimplePU<boolean>;
    get multimedia() {
        return this.__multimedia.get();
    }
    set multimedia(newValue: boolean) {
        this.__multimedia.set(newValue);
    }
    private onBack: () => void;
    private onQuery: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    Chip(label: string, active: boolean, onTap: () => void, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.layoutWeight(1);
            Text.textAlign(TextAlign.Center);
            Text.maxLines(1);
            Text.fontSize(9);
            Text.fontColor(active ? '#FFFFFFFF' : this.palette().muted);
            Text.padding({ top: 8, bottom: 8 });
            Text.backgroundColor(active ? this.palette().primary : this.palette().surface);
            Text.border({ width: 1, color: active ? this.palette().primary : this.palette().line });
            Text.borderRadius(16);
            Text.onClick(onTap);
        }, Text);
        Text.pop();
    }
    FilterPanel(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding(14);
            Column.backgroundColor(this.palette().surface);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('节次');
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 6 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.Chip.bind(this)(item, this.slot === item, () => this.slot = item);
            };
            this.forEachUpdateFunction(elmtId, ['1-2节', '3-4节', '5-6节', '7-8节'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832143, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('容量');
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 6 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.Chip.bind(this)(item, this.capacity === item, () => this.capacity = item);
            };
            this.forEachUpdateFunction(elmtId, ['全部容量', '>=40座', '>=80座', '>=100座'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125833333, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('仅显示有多媒体设备');
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('投影、音响等教学设备');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Toggle.create({ type: ToggleType.Switch, isOn: this.multimedia });
            Toggle.onChange((value: boolean) => this.multimedia = value);
        }, Toggle);
        Toggle.pop();
        Row.pop();
        Column.pop();
    }
    ClassroomCard(item: ClassroomAvailability, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(11);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777227, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width(105);
            Image.height(78);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(12);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 6 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.classroom?.name ?? item.name ?? '教室');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.classroom?.building ?? item.building ?? '教学楼'}  ·  ${item.classroom?.capacity ?? item.capacity ?? 0} 座`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 5 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.slot);
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.padding({ left: 7, right: 7, top: 4, bottom: 4 });
            Text.backgroundColor(this.palette().soft);
            Text.borderRadius(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if ((item.classroom?.has_multimedia ?? item.has_multimedia) !== false) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('多媒体');
                        Text.fontColor(this.palette().success);
                        Text.fontSize(9);
                        Text.padding({ left: 7, right: 7, top: 4, bottom: 4 });
                        Text.backgroundColor('#FFEAF9F3');
                        Text.borderRadius(10);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        Row.pop();
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
                    let componentCall = new SecondaryHeader(this, { title: '空教室查询', subtitle: '基于课程占用数据，帮你快速找到可用教室', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/classrooms/ClassroomsPage.ets", line: 74, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: '空教室查询',
                            subtitle: '基于课程占用数据，帮你快速找到可用教室',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: '空教室查询', subtitle: '基于课程占用数据，帮你快速找到可用教室', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777227, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(170);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(20);
        }, Image);
        this.FilterPanel.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithChild({ type: ButtonType.Capsule });
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.onClick(() => this.onQuery());
        }, Button);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.width(20);
                        LoadingProgress.height(20);
                        LoadingProgress.color('#FFFFFFFF');
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.loading ? '正在查询...' : '查询空闲教室');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        Button.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Rect.create();
            Rect.width(5);
            Rect.height(24);
            Rect.fill(this.palette().primary);
            Rect.radius(3);
        }, Rect);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('推荐空教室');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`共 ${this.classrooms.length} 间可用`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (!this.loading && this.classrooms.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('当前条件下没有可用教室，请调整筛选条件。');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding({ top: 24, bottom: 28 });
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = _item => {
                            const item = _item;
                            this.ClassroomCard.bind(this)(item);
                        };
                        this.forEachUpdateFunction(elmtId, this.classrooms, forEachItemGenFunction);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

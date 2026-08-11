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
    constructor(y4, z4, a5, b5 = -1, c5 = undefined, d5) {
        super(y4, a5, b5, d5);
        if (typeof c5 === "function") {
            this.paramsGenerator_ = c5;
        }
        this.__classrooms = new SynchedPropertyObjectOneWayPU(z4.classrooms, this, "classrooms");
        this.__loading = new SynchedPropertySimpleOneWayPU(z4.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(z4.darkMode, this, "darkMode");
        this.__slot = new ObservedPropertySimplePU('1-2节', this, "slot");
        this.__capacity = new ObservedPropertySimplePU('全部容量', this, "capacity");
        this.__multimedia = new ObservedPropertySimplePU(true, this, "multimedia");
        this.onBack = () => { };
        this.onQuery = () => { };
        this.setInitiallyProvidedValue(z4);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(x4: ClassroomsPage_Params) {
        if (x4.classrooms === undefined) {
            this.__classrooms.set([]);
        }
        if (x4.loading === undefined) {
            this.__loading.set(false);
        }
        if (x4.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (x4.slot !== undefined) {
            this.slot = x4.slot;
        }
        if (x4.capacity !== undefined) {
            this.capacity = x4.capacity;
        }
        if (x4.multimedia !== undefined) {
            this.multimedia = x4.multimedia;
        }
        if (x4.onBack !== undefined) {
            this.onBack = x4.onBack;
        }
        if (x4.onQuery !== undefined) {
            this.onQuery = x4.onQuery;
        }
    }
    updateStateVars(w4: ClassroomsPage_Params) {
        this.__classrooms.reset(w4.classrooms);
        this.__loading.reset(w4.loading);
        this.__darkMode.reset(w4.darkMode);
    }
    purgeVariableDependenciesOnElmtId(v4) {
        this.__classrooms.purgeDependencyOnElmtId(v4);
        this.__loading.purgeDependencyOnElmtId(v4);
        this.__darkMode.purgeDependencyOnElmtId(v4);
        this.__slot.purgeDependencyOnElmtId(v4);
        this.__capacity.purgeDependencyOnElmtId(v4);
        this.__multimedia.purgeDependencyOnElmtId(v4);
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
    set classrooms(u4: ClassroomAvailability[]) {
        this.__classrooms.set(u4);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(t4: boolean) {
        this.__loading.set(t4);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(s4: boolean) {
        this.__darkMode.set(s4);
    }
    private __slot: ObservedPropertySimplePU<string>;
    get slot() {
        return this.__slot.get();
    }
    set slot(r4: string) {
        this.__slot.set(r4);
    }
    private __capacity: ObservedPropertySimplePU<string>;
    get capacity() {
        return this.__capacity.get();
    }
    set capacity(q4: string) {
        this.__capacity.set(q4);
    }
    private __multimedia: ObservedPropertySimplePU<boolean>;
    get multimedia() {
        return this.__multimedia.get();
    }
    set multimedia(p4: boolean) {
        this.__multimedia.set(p4);
    }
    private onBack: () => void;
    private onQuery: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    Chip(j4: string, k4: boolean, l4: () => void, m4 = null) {
        this.observeComponentCreation2((n4, o4) => {
            Text.create(j4);
            Text.layoutWeight(1);
            Text.textAlign(TextAlign.Center);
            Text.maxLines(1);
            Text.fontSize(9);
            Text.fontColor(k4 ? '#FFFFFFFF' : this.palette().muted);
            Text.padding({ top: 8, bottom: 8 });
            Text.backgroundColor(k4 ? this.palette().primary : this.palette().surface);
            Text.border({ width: 1, color: k4 ? this.palette().primary : this.palette().line });
            Text.borderRadius(16);
            Text.onClick(l4);
        }, Text);
        Text.pop();
    }
    FilterPanel(p2 = null) {
        this.observeComponentCreation2((h4, i4) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding(14);
            Column.backgroundColor(this.palette().surface);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((f4, g4) => {
            Row.create({ space: 8 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((d4, e4) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((b4, c4) => {
            Text.create('节次');
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((z3, a4) => {
            Row.create({ space: 6 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((u3, v3) => {
            ForEach.create();
            const w3 = x3 => {
                const y3 = x3;
                this.Chip.bind(this)(y3, this.slot === y3, () => this.slot = y3);
            };
            this.forEachUpdateFunction(u3, ['1-2节', '3-4节', '5-6节', '7-8节'], w3);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((s3, t3) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.observeComponentCreation2((q3, r3) => {
            Row.create({ space: 8 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((o3, p3) => {
            SymbolGlyph.create({ "id": 125832143, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((m3, n3) => {
            Text.create('容量');
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((k3, l3) => {
            Row.create({ space: 6 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((f3, g3) => {
            ForEach.create();
            const h3 = i3 => {
                const j3 = i3;
                this.Chip.bind(this)(j3, this.capacity === j3, () => this.capacity = j3);
            };
            this.forEachUpdateFunction(f3, ['全部容量', '>=40座', '>=80座', '>=100座'], h3);
        }, ForEach);
        ForEach.pop();
        Row.pop();
        this.observeComponentCreation2((d3, e3) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.observeComponentCreation2((b3, c3) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((z2, a3) => {
            SymbolGlyph.create({ "id": 125833333, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((x2, y2) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((v2, w2) => {
            Text.create('仅显示有多媒体设备');
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t2, u2) => {
            Text.create('投影、音响等教学设备');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((q2, r2) => {
            Toggle.create({ type: ToggleType.Switch, isOn: this.multimedia });
            Toggle.onChange((s2: boolean) => this.multimedia = s2);
        }, Toggle);
        Toggle.pop();
        Row.pop();
        Column.pop();
    }
    ClassroomCard(t1: ClassroomAvailability, u1 = null) {
        this.observeComponentCreation2((n2, o2) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(11);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((l2, m2) => {
            Image.create({ "id": 16777227, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width(105);
            Image.height(78);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(12);
        }, Image);
        this.observeComponentCreation2((j2, k2) => {
            Column.create({ space: 6 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((h2, i2) => {
            Text.create(t1.classroom?.name ?? t1.name ?? '教室');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((f2, g2) => {
            Text.create(`${t1.classroom?.building ?? t1.building ?? '教学楼'}  ·  ${t1.classroom?.capacity ?? t1.capacity ?? 0} 座`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((d2, e2) => {
            Row.create({ space: 5 });
        }, Row);
        this.observeComponentCreation2((b2, c2) => {
            Text.create(this.slot);
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.padding({ left: 7, right: 7, top: 4, bottom: 4 });
            Text.backgroundColor(this.palette().soft);
            Text.borderRadius(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((x1, y1) => {
            If.create();
            if ((t1.classroom?.has_multimedia ?? t1.has_multimedia) !== false) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((z1, a2) => {
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
        this.observeComponentCreation2((v1, w1) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((r1, s1) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((n1, o1) => {
                if (o1) {
                    let p1 = new SecondaryHeader(this, { title: '空教室查询', subtitle: '基于课程占用数据，帮你快速找到可用教室', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, n1, () => { }, { page: "entry/src/main/ets/features/classrooms/ClassroomsPage.ets", line: 74, col: 7 });
                    ViewPU.create(p1);
                    let q1 = () => {
                        return {
                            title: '空教室查询',
                            subtitle: '基于课程占用数据，帮你快速找到可用教室',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    p1.paramsGenerator_ = q1;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(n1, {
                        title: '空教室查询', subtitle: '基于课程占用数据，帮你快速找到可用教室', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((l1, m1) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((j1, k1) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((h1, i1) => {
            Image.create({ "id": 16777227, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(170);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(20);
        }, Image);
        this.FilterPanel.bind(this)();
        this.observeComponentCreation2((f1, g1) => {
            Button.createWithChild({ type: ButtonType.Capsule });
            Button.width('100%');
            Button.height(52);
            Button.backgroundColor(this.palette().primary);
            Button.onClick(() => this.onQuery());
        }, Button);
        this.observeComponentCreation2((d1, e1) => {
            Row.create({ space: 8 });
        }, Row);
        this.observeComponentCreation2((x, y) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((b1, c1) => {
                        LoadingProgress.create();
                        LoadingProgress.width(20);
                        LoadingProgress.height(20);
                        LoadingProgress.color('#FFFFFFFF');
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((z, a1) => {
                        SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((v, w) => {
            Text.create(this.loading ? '正在查询...' : '查询空闲教室');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        Button.pop();
        this.observeComponentCreation2((t, u) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((r, s) => {
            Row.create({ space: 8 });
        }, Row);
        this.observeComponentCreation2((p, q) => {
            Rect.create();
            Rect.width(5);
            Rect.height(24);
            Rect.fill(this.palette().primary);
            Rect.radius(3);
        }, Rect);
        this.observeComponentCreation2((n, o) => {
            Text.create('推荐空教室');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((l, m) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((j, k) => {
            Text.create(`共 ${this.classrooms.length} 间可用`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((a, b) => {
            If.create();
            if (!this.loading && this.classrooms.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((h, i) => {
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
                    this.observeComponentCreation2((c, d) => {
                        ForEach.create();
                        const e = f => {
                            const g = f;
                            this.ClassroomCard.bind(this)(g);
                        };
                        this.forEachUpdateFunction(c, this.classrooms, e);
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

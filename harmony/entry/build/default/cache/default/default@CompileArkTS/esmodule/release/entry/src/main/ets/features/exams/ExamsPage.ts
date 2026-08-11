if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface ExamsPage_Params {
    exams?: ExamItem[];
    loading?: boolean;
    darkMode?: boolean;
    filter?: string;
    onBack?: () => void;
    onRefresh?: () => void;
}
import type { ExamItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class ExamsPage extends ViewPU {
    constructor(g9, h9, i9, j9 = -1, k9 = undefined, l9) {
        super(g9, i9, j9, l9);
        if (typeof k9 === "function") {
            this.paramsGenerator_ = k9;
        }
        this.__exams = new SynchedPropertyObjectOneWayPU(h9.exams, this, "exams");
        this.__loading = new SynchedPropertySimpleOneWayPU(h9.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(h9.darkMode, this, "darkMode");
        this.__filter = new ObservedPropertySimplePU('全部', this, "filter");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(h9);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(f9: ExamsPage_Params) {
        if (f9.exams === undefined) {
            this.__exams.set([]);
        }
        if (f9.loading === undefined) {
            this.__loading.set(false);
        }
        if (f9.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (f9.filter !== undefined) {
            this.filter = f9.filter;
        }
        if (f9.onBack !== undefined) {
            this.onBack = f9.onBack;
        }
        if (f9.onRefresh !== undefined) {
            this.onRefresh = f9.onRefresh;
        }
    }
    updateStateVars(e9: ExamsPage_Params) {
        this.__exams.reset(e9.exams);
        this.__loading.reset(e9.loading);
        this.__darkMode.reset(e9.darkMode);
    }
    purgeVariableDependenciesOnElmtId(d9) {
        this.__exams.purgeDependencyOnElmtId(d9);
        this.__loading.purgeDependencyOnElmtId(d9);
        this.__darkMode.purgeDependencyOnElmtId(d9);
        this.__filter.purgeDependencyOnElmtId(d9);
    }
    aboutToBeDeleted() {
        this.__exams.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__filter.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __exams: SynchedPropertySimpleOneWayPU<ExamItem[]>;
    get exams() {
        return this.__exams.get();
    }
    set exams(c9: ExamItem[]) {
        this.__exams.set(c9);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(b9: boolean) {
        this.__loading.set(b9);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(a9: boolean) {
        this.__darkMode.set(a9);
    }
    private __filter: ObservedPropertySimplePU<string>;
    get filter() {
        return this.__filter.get();
    }
    set filter(z8: string) {
        this.__filter.set(z8);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    Hero(a8 = null) {
        this.observeComponentCreation2((x8, y8) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(188);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((v8, w8) => {
            Image.create({ "id": 16777226, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(188);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((t8, u8) => {
            Column.create({ space: 8 });
            Column.width('100%');
            Column.padding({ left: 17, right: 17, bottom: 16 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((r8, s8) => {
            Text.create('距离最近考试');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((p8, q8) => {
            Text.create(this.exams.length > 0 ? this.exams[0].course_name : '暂无考试安排');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((n8, o8) => {
            Row.create({ space: 14 });
        }, Row);
        this.observeComponentCreation2((l8, m8) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((j8, k8) => {
            SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((h8, i8) => {
            Text.create(this.exams.length > 0 ? this.exams[0].exam_date : '安心备考');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((f8, g8) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((d8, e8) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((b8, c8) => {
            Text.create(this.exams.length > 0 ? (this.exams[0].location ?? '地点待定') : '暂无地点');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        Row.pop();
        Column.pop();
        Stack.pop();
    }
    FilterTabs(q7 = null) {
        this.observeComponentCreation2((y7, z7) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((r7, s7) => {
            ForEach.create();
            const t7 = u7 => {
                const v7 = u7;
                this.observeComponentCreation2((w7, x7) => {
                    Text.create(v7);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(12);
                    Text.fontColor(this.filter === v7 ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontWeight(this.filter === v7 ? FontWeight.Bold : FontWeight.Normal);
                    Text.padding({ top: 9, bottom: 9 });
                    Text.backgroundColor(this.filter === v7 ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.filter === v7 ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.filter = v7);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(r7, ['全部', '未开始', '已结束'], t7);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    ExamCard(o6: ExamItem, p6 = null) {
        this.observeComponentCreation2((o7, p7) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((m7, n7) => {
            Column.create({ space: 2 });
            Column.width(58);
            Column.height(58);
            Column.justifyContent(FlexAlign.Center);
            Column.backgroundColor(this.palette().soft);
            Column.borderRadius(14);
        }, Column);
        this.observeComponentCreation2((k7, l7) => {
            Text.create(o6.exam_date.substring(Math.max(0, o6.exam_date.length - 5)));
            Text.fontColor(this.palette().primary);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((i7, j7) => {
            Text.create(o6.exam_type ?? '考试');
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((g7, h7) => {
            Column.create({ space: 5 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((e7, f7) => {
            Text.create(o6.course_name);
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((c7, d7) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((a7, b7) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((y6, z6) => {
            Text.create(`${o6.start_time ?? '--:--'} - ${o6.end_time ?? '--:--'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((w6, x6) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((u6, v6) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((s6, t6) => {
            Text.create(`${o6.location ?? '地点待定'}  ${o6.seat_number ?? ''}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((q6, r6) => {
            SymbolGlyph.create({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([o6.reminder_enabled === false ? this.palette().muted : this.palette().primary]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((m6, n6) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((i6, j6) => {
                if (j6) {
                    let k6 = new SecondaryHeader(this, { title: '考试安排', subtitle: '每一场考试，都替你记得清清楚楚', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, i6, () => { }, { page: "entry/src/main/ets/features/exams/ExamsPage.ets", line: 73, col: 7 });
                    ViewPU.create(k6);
                    let l6 = () => {
                        return {
                            title: '考试安排',
                            subtitle: '每一场考试，都替你记得清清楚楚',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    k6.paramsGenerator_ = l6;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(i6, {
                        title: '考试安排', subtitle: '每一场考试，都替你记得清清楚楚', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((g6, h6) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((e6, f6) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.Hero.bind(this)();
        this.FilterTabs.bind(this)();
        this.observeComponentCreation2((c6, d6) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((a6, b6) => {
            Text.create('考试列表');
            Text.fontColor(this.palette().text);
            Text.fontSize(18);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((y5, z5) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((w5, x5) => {
            Text.create(`${this.exams.length} 场`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((e5, f5) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((u5, v5) => {
                        LoadingProgress.create();
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 28 });
                    }, LoadingProgress);
                });
            }
            else if (this.exams.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((s5, t5) => {
                        Column.create({ space: 10 });
                        Column.width('100%');
                        Column.padding({ top: 34, bottom: 34 });
                        Column.onClick(() => this.onRefresh());
                    }, Column);
                    this.observeComponentCreation2((q5, r5) => {
                        SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(34);
                        SymbolGlyph.fontColor([this.palette().muted]);
                    }, SymbolGlyph);
                    this.observeComponentCreation2((o5, p5) => {
                        Text.create('暂无考试安排');
                        Text.fontColor(this.palette().text);
                        Text.fontSize(14);
                        Text.fontWeight(FontWeight.Medium);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((m5, n5) => {
                        Text.create('下拉刷新或稍后再查看');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(11);
                    }, Text);
                    Text.pop();
                    Column.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((g5, h5) => {
                        ForEach.create();
                        const i5 = k5 => {
                            const l5 = k5;
                            this.ExamCard.bind(this)(l5);
                        };
                        this.forEachUpdateFunction(g5, this.exams, i5, (j5: ExamItem) => j5.id, false, false);
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

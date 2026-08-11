if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface ExamsPage_Params {
    exams?: ExamItem[];
    loading?: boolean;
    darkMode?: boolean;
    filter?: string;
    selectedId?: string;
    onBack?: () => void;
    onRefresh?: () => void;
}
import type { ExamItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class ExamsPage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__exams = new SynchedPropertyObjectOneWayPU(params.exams, this, "exams");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__filter = new ObservedPropertySimplePU('全部', this, "filter");
        this.__selectedId = new ObservedPropertySimplePU('', this, "selectedId");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: ExamsPage_Params) {
        if (params.exams === undefined) {
            this.__exams.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.filter !== undefined) {
            this.filter = params.filter;
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
    }
    updateStateVars(params: ExamsPage_Params) {
        this.__exams.reset(params.exams);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__exams.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__filter.purgeDependencyOnElmtId(rmElmtId);
        this.__selectedId.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__exams.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__filter.aboutToBeDeleted();
        this.__selectedId.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __exams: SynchedPropertySimpleOneWayPU<ExamItem[]>;
    get exams() {
        return this.__exams.get();
    }
    set exams(newValue: ExamItem[]) {
        this.__exams.set(newValue);
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
    private __filter: ObservedPropertySimplePU<string>;
    get filter() {
        return this.__filter.get();
    }
    set filter(newValue: string) {
        this.__filter.set(newValue);
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
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    selectedExam(): ExamItem | undefined { return this.exams.find((item: ExamItem) => item.id === this.selectedId); }
    Hero(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(188);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777226, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(188);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 8 });
            Column.width('100%');
            Column.padding({ left: 17, right: 17, bottom: 16 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('距离最近考试');
            Text.fontColor('#E6FFFFFF');
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.exams.length > 0 ? this.exams[0].course_name : '暂无考试安排');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 14 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.exams.length > 0 ? this.exams[0].exam_date : '安心备考');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(14);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
    FilterTabs(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.observeComponentCreation2((elmtId, isInitialRender) => {
                    Text.create(item);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(12);
                    Text.fontColor(this.filter === item ? '#FFFFFFFF' : this.palette().muted);
                    Text.fontWeight(this.filter === item ? FontWeight.Bold : FontWeight.Normal);
                    Text.padding({ top: 9, bottom: 9 });
                    Text.backgroundColor(this.filter === item ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.filter === item ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.filter = item);
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(elmtId, ['全部', '未开始', '已结束'], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    ExamCard(exam: ExamItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(18);
            Row.onClick(() => this.selectedId = exam.id);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.width(58);
            Column.height(58);
            Column.justifyContent(FlexAlign.Center);
            Column.backgroundColor(this.palette().soft);
            Column.borderRadius(14);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(exam.exam_date.substring(Math.max(0, exam.exam_date.length - 5)));
            Text.fontColor(this.palette().primary);
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(exam.exam_type ?? '考试');
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 5 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(exam.course_name);
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${exam.start_time ?? '--:--'} - ${exam.end_time ?? '--:--'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(12);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${exam.location ?? '地点待定'}  ${exam.seat_number ?? ''}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([exam.reminder_enabled === false ? this.palette().muted : this.palette().primary]);
        }, SymbolGlyph);
        Row.pop();
    }
    Detail(exam: ExamItem, parent = null) {
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
            Stack.create({ alignContent: Alignment.BottomStart });
            Stack.width('100%');
            Stack.height(202);
            Stack.borderRadius(20);
            Stack.clip(true);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777226, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height(202);
            Image.objectFit(ImageFit.Cover);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 5 });
            Column.padding({ left: 16, right: 16, bottom: 16 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(exam.course_name);
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(exam.exam_type ?? '课程考试');
            Text.fontColor('#DFFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 14, right: 14 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.DetailRow.bind(this)({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '考试日期', exam.exam_date);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.DetailRow.bind(this)({ "id": 125832302, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '考试时间', `${exam.start_time ?? '--:--'} - ${exam.end_time ?? '--:--'}`);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.DetailRow.bind(this)({ "id": 125832174, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '考试地点', exam.location ?? '待定');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.DetailRow.bind(this)({ "id": 125832135, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '座位号', exam.seat_number ?? '待定');
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if ((exam.notes ?? '').length > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create(exam.notes ?? '');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.lineHeight(19);
                        Text.width('100%');
                        Text.padding(14);
                        Text.backgroundColor(this.palette().surface);
                        Text.borderRadius(16);
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
        Column.pop();
        Scroll.pop();
    }
    DetailRow(symbol: Resource, label: string, value: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 14, bottom: 14 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.fontSize(19);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
            Text.width(74);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(value);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Medium);
            Text.layoutWeight(1);
        }, Text);
        Text.pop();
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
                    let componentCall = new SecondaryHeader(this, { title: this.selectedId.length > 0 ? '考试详情' : '考试安排', subtitle: this.selectedId.length > 0 ? '时间、地点与座位信息' : '每一场考试，都替你记得清清楚楚', darkMode: this.darkMode, onBack: () => this.selectedId.length > 0 ? this.selectedId = '' : this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/exams/ExamsPage.ets", line: 110, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: this.selectedId.length > 0 ? '考试详情' : '考试安排',
                            subtitle: this.selectedId.length > 0 ? '时间、地点与座位信息' : '每一场考试，都替你记得清清楚楚',
                            darkMode: this.darkMode,
                            onBack: () => this.selectedId.length > 0 ? this.selectedId = '' : this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: this.selectedId.length > 0 ? '考试详情' : '考试安排', subtitle: this.selectedId.length > 0 ? '时间、地点与座位信息' : '每一场考试，都替你记得清清楚楚', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.selectedExam() !== undefined) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.Detail.bind(this)(this.selectedExam()!);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
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
                    this.Hero.bind(this)();
                    this.FilterTabs.bind(this)();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Row.create();
                        Row.width('100%');
                    }, Row);
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('考试列表');
                        Text.fontColor(this.palette().text);
                        Text.fontSize(18);
                        Text.fontWeight(FontWeight.Bold);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Blank.create();
                    }, Blank);
                    Blank.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create(`${this.exams.length} 场`);
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(11);
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
                                    LoadingProgress.margin({ top: 28 });
                                }, LoadingProgress);
                            });
                        }
                        else if (this.exams.length === 0) {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Column.create({ space: 10 });
                                    Column.width('100%');
                                    Column.padding({ top: 34, bottom: 34 });
                                    Column.onClick(() => this.onRefresh());
                                }, Column);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    SymbolGlyph.create({ "id": 125832312, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                                    SymbolGlyph.fontSize(34);
                                    SymbolGlyph.fontColor([this.palette().muted]);
                                }, SymbolGlyph);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Text.create('暂无考试安排');
                                    Text.fontColor(this.palette().text);
                                    Text.fontSize(14);
                                    Text.fontWeight(FontWeight.Medium);
                                }, Text);
                                Text.pop();
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    ForEach.create();
                                    const forEachItemGenFunction = _item => {
                                        const exam = _item;
                                        this.ExamCard.bind(this)(exam);
                                    };
                                    this.forEachUpdateFunction(elmtId, this.exams, forEachItemGenFunction, (exam: ExamItem) => exam.id, false, false);
                                }, ForEach);
                                ForEach.pop();
                            });
                        }
                    }, If);
                    If.pop();
                    Column.pop();
                    Scroll.pop();
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

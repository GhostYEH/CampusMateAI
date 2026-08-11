if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface FocusPage_Params {
    sessions?: StudySession[];
    activeSession?: StudySession;
    loading?: boolean;
    darkMode?: boolean;
    mode?: string;
    secondsLeft?: number;
    running?: boolean;
    timerId?: number;
    onBack?: () => void;
    onStart?: () => void;
    onPause?: () => void;
    onResume?: () => void;
    onFinish?: () => void;
}
import type { StudySession } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class FocusPage extends ViewPU {
    constructor(t13, u13, v13, w13 = -1, x13 = undefined, y13) {
        super(t13, v13, w13, y13);
        if (typeof x13 === "function") {
            this.paramsGenerator_ = x13;
        }
        this.__sessions = new SynchedPropertyObjectOneWayPU(u13.sessions, this, "sessions");
        this.__activeSession = new SynchedPropertyObjectOneWayPU(u13.activeSession, this, "activeSession");
        this.__loading = new SynchedPropertySimpleOneWayPU(u13.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(u13.darkMode, this, "darkMode");
        this.__mode = new ObservedPropertySimplePU('专注', this, "mode");
        this.__secondsLeft = new ObservedPropertySimplePU(25 * 60, this, "secondsLeft");
        this.__running = new ObservedPropertySimplePU(false, this, "running");
        this.timerId = -1;
        this.onBack = () => { };
        this.onStart = () => { };
        this.onPause = () => { };
        this.onResume = () => { };
        this.onFinish = () => { };
        this.setInitiallyProvidedValue(u13);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(s13: FocusPage_Params) {
        if (s13.sessions === undefined) {
            this.__sessions.set([]);
        }
        if (s13.activeSession === undefined) {
            this.__activeSession.set(undefined);
        }
        if (s13.loading === undefined) {
            this.__loading.set(false);
        }
        if (s13.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (s13.mode !== undefined) {
            this.mode = s13.mode;
        }
        if (s13.secondsLeft !== undefined) {
            this.secondsLeft = s13.secondsLeft;
        }
        if (s13.running !== undefined) {
            this.running = s13.running;
        }
        if (s13.timerId !== undefined) {
            this.timerId = s13.timerId;
        }
        if (s13.onBack !== undefined) {
            this.onBack = s13.onBack;
        }
        if (s13.onStart !== undefined) {
            this.onStart = s13.onStart;
        }
        if (s13.onPause !== undefined) {
            this.onPause = s13.onPause;
        }
        if (s13.onResume !== undefined) {
            this.onResume = s13.onResume;
        }
        if (s13.onFinish !== undefined) {
            this.onFinish = s13.onFinish;
        }
    }
    updateStateVars(r13: FocusPage_Params) {
        this.__sessions.reset(r13.sessions);
        this.__activeSession.reset(r13.activeSession);
        this.__loading.reset(r13.loading);
        this.__darkMode.reset(r13.darkMode);
    }
    purgeVariableDependenciesOnElmtId(q13) {
        this.__sessions.purgeDependencyOnElmtId(q13);
        this.__activeSession.purgeDependencyOnElmtId(q13);
        this.__loading.purgeDependencyOnElmtId(q13);
        this.__darkMode.purgeDependencyOnElmtId(q13);
        this.__mode.purgeDependencyOnElmtId(q13);
        this.__secondsLeft.purgeDependencyOnElmtId(q13);
        this.__running.purgeDependencyOnElmtId(q13);
    }
    aboutToBeDeleted() {
        this.__sessions.aboutToBeDeleted();
        this.__activeSession.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__mode.aboutToBeDeleted();
        this.__secondsLeft.aboutToBeDeleted();
        this.__running.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __sessions: SynchedPropertySimpleOneWayPU<StudySession[]>;
    get sessions() {
        return this.__sessions.get();
    }
    set sessions(p13: StudySession[]) {
        this.__sessions.set(p13);
    }
    private __activeSession?: SynchedPropertySimpleOneWayPU<StudySession>;
    get activeSession() {
        return this.__activeSession.get();
    }
    set activeSession(o13: StudySession) {
        this.__activeSession.set(o13);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(n13: boolean) {
        this.__loading.set(n13);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(m13: boolean) {
        this.__darkMode.set(m13);
    }
    private __mode: ObservedPropertySimplePU<string>;
    get mode() {
        return this.__mode.get();
    }
    set mode(l13: string) {
        this.__mode.set(l13);
    }
    private __secondsLeft: ObservedPropertySimplePU<number>;
    get secondsLeft() {
        return this.__secondsLeft.get();
    }
    set secondsLeft(k13: number) {
        this.__secondsLeft.set(k13);
    }
    private __running: ObservedPropertySimplePU<boolean>;
    get running() {
        return this.__running.get();
    }
    set running(j13: boolean) {
        this.__running.set(j13);
    }
    private timerId: number;
    private onBack: () => void;
    private onStart: () => void;
    private onPause: () => void;
    private onResume: () => void;
    private onFinish: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    aboutToDisappear(): void { this.stopClock(); }
    totalSeconds(): number { return this.mode === '专注' ? 25 * 60 : this.mode === '短休息' ? 5 * 60 : 15 * 60; }
    timeText(): string {
        const h13 = Math.floor(this.secondsLeft / 60).toString().padStart(2, '0');
        const i13 = (this.secondsLeft % 60).toString().padStart(2, '0');
        return `${h13}:${i13}`;
    }
    stopClock(): void {
        if (this.timerId >= 0) {
            clearInterval(this.timerId);
            this.timerId = -1;
        }
    }
    startClock(): void {
        if (this.running) {
            this.running = false;
            this.stopClock();
            this.onPause();
            return;
        }
        this.running = true;
        if (this.secondsLeft === this.totalSeconds())
            this.onStart();
        else
            this.onResume();
        this.timerId = setInterval(() => {
            if (this.secondsLeft > 0)
                this.secondsLeft -= 1;
            else {
                this.running = false;
                this.stopClock();
                this.onFinish();
            }
        }, 1000);
    }
    resetMode(g13: string): void { this.stopClock(); this.running = false; this.mode = g13; this.secondsLeft = this.totalSeconds(); }
    ModeTabs(w12 = null) {
        this.observeComponentCreation2((e13, f13) => {
            Row.create({ space: 7 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((x12, y12) => {
            ForEach.create();
            const z12 = a13 => {
                const b13 = a13;
                this.observeComponentCreation2((c13, d13) => {
                    Text.create(b13);
                    Text.layoutWeight(1);
                    Text.textAlign(TextAlign.Center);
                    Text.fontSize(11);
                    Text.padding({ top: 8, bottom: 8 });
                    Text.fontColor(this.mode === b13 ? '#FFFFFFFF' : this.palette().muted);
                    Text.backgroundColor(this.mode === b13 ? this.palette().primary : this.palette().surface);
                    Text.border({ width: 1, color: this.mode === b13 ? this.palette().primary : this.palette().line });
                    Text.borderRadius(18);
                    Text.onClick(() => this.resetMode(b13));
                }, Text);
                Text.pop();
            };
            this.forEachUpdateFunction(x12, ['专注', '短休息', '长休息'], z12);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    TimerCard(r11 = null) {
        this.observeComponentCreation2((u12, v12) => {
            Column.create({ space: 14 });
            Column.width('100%');
            Column.padding({ top: 20, left: 16, right: 16, bottom: 18 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(22);
        }, Column);
        this.observeComponentCreation2((s12, t12) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(230);
            Stack.height(230);
        }, Stack);
        this.observeComponentCreation2((q12, r12) => {
            Progress.create({ value: this.totalSeconds() - this.secondsLeft, total: this.totalSeconds(), type: ProgressType.Ring });
            Progress.width(220);
            Progress.height(220);
            Progress.color(this.palette().primary);
            Progress.backgroundColor(this.palette().soft);
            Progress.style({ strokeWidth: 10 });
        }, Progress);
        this.observeComponentCreation2((o12, p12) => {
            Column.create({ space: 6 });
        }, Column);
        this.observeComponentCreation2((m12, n12) => {
            SymbolGlyph.create({ "id": 125832304, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(24);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((k12, l12) => {
            Text.create(this.timeText());
            Text.fontColor(this.palette().primary);
            Text.fontSize(44);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((i12, j12) => {
            Text.create(this.running ? '专注进行中' : this.secondsLeft !== this.totalSeconds() ? '已暂停' : '准备开始');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        Stack.pop();
        this.observeComponentCreation2((g12, h12) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((e12, f12) => {
            Button.createWithChild({ type: ButtonType.Capsule });
            Button.layoutWeight(1);
            Button.height(48);
            Button.backgroundColor(this.palette().primary);
            Button.onClick(() => this.startClock());
        }, Button);
        this.observeComponentCreation2((c12, d12) => {
            Row.create({ space: 7 });
        }, Row);
        this.observeComponentCreation2((w11, x11) => {
            If.create();
            if (this.running) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((a12, b12) => {
                        SymbolGlyph.create({ "id": 125831176, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((y11, z11) => {
                        SymbolGlyph.create({ "id": 125831825, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((u11, v11) => {
            Text.create(this.running ? '暂停' : this.secondsLeft !== this.totalSeconds() ? '继续' : '开始专注');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        Button.pop();
        this.observeComponentCreation2((s11, t11) => {
            Button.createWithLabel('结束');
            Button.width(92);
            Button.height(48);
            Button.backgroundColor(this.palette().soft);
            Button.fontColor(this.palette().primary);
            Button.onClick(() => { this.stopClock(); this.running = false; this.secondsLeft = this.totalSeconds(); this.onFinish(); });
        }, Button);
        Button.pop();
        Row.pop();
        Column.pop();
    }
    Record(d11: StudySession, e11 = null) {
        this.observeComponentCreation2((p11, q11) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 10, bottom: 10 });
        }, Row);
        this.observeComponentCreation2((n11, o11) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((l11, m11) => {
            SymbolGlyph.create({ "id": 125832305, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(19);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((j11, k11) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((h11, i11) => {
            Text.create(`${d11.goal ?? '专注学习'} · ${d11.started_at.substring(0, Math.min(10, d11.started_at.length))}`);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((f11, g11) => {
            Text.create(`${Math.max(1, Math.floor(d11.duration_seconds / 60))} 分钟 · ${d11.status === 'completed' ? '已完成' : '进行中'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((b11, c11) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((x10, y10) => {
                if (y10) {
                    let z10 = new SecondaryHeader(this, { title: '专注自习', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, x10, () => { }, { page: "entry/src/main/ets/features/focus/FocusPage.ets", line: 95, col: 7 });
                    ViewPU.create(z10);
                    let a11 = () => {
                        return {
                            title: '专注自习',
                            subtitle: '一次只做一件事，让注意力回到当下',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    z10.paramsGenerator_ = a11;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(x10, {
                        title: '专注自习', subtitle: '一次只做一件事，让注意力回到当下', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((v10, w10) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((t10, u10) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 20 });
        }, Column);
        this.ModeTabs.bind(this)();
        this.TimerCard.bind(this)();
        this.observeComponentCreation2((r10, s10) => {
            Row.create({ space: 8 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((p10, q10) => {
            SymbolGlyph.create({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        this.observeComponentCreation2((n10, o10) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((l10, m10) => {
            Text.create('学习状态辅助');
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j10, k10) => {
            Text.create('鸿蒙端不上传画面，专注记录已真实同步后端');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
        this.observeComponentCreation2((h10, i10) => {
            Text.create('专注记录');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((f10, g10) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((o9, p9) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((d10, e10) => {
                        LoadingProgress.create();
                        LoadingProgress.width(32);
                        LoadingProgress.height(32);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin(28);
                    }, LoadingProgress);
                });
            }
            else if (this.sessions.length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((b10, c10) => {
                        Text.create('还没有专注记录');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding(28);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((q9, r9) => {
                        ForEach.create();
                        const s9 = (u9, v9: number) => {
                            const w9 = u9;
                            this.Record.bind(this)(w9);
                            this.observeComponentCreation2((x9, y9) => {
                                If.create();
                                if (v9 < this.sessions.length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((z9, a10) => {
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
                        this.forEachUpdateFunction(q9, this.sessions, s9, (t9: StudySession) => t9.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        this.observeComponentCreation2((m9, n9) => {
            Blank.create();
            Blank.height(18);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

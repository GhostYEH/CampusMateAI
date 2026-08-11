if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface CounselorPage_Params {
    messages?: ChatMessage[];
    sending?: boolean;
    darkMode?: boolean;
    input?: string;
    onSend?: () => void;
}
import type { ChatMessage } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
export class CounselorPage extends ViewPU {
    constructor(a3, b3, c3, d3 = -1, e3 = undefined, f3) {
        super(a3, c3, d3, f3);
        if (typeof e3 === "function") {
            this.paramsGenerator_ = e3;
        }
        this.__messages = new SynchedPropertyObjectOneWayPU(b3.messages, this, "messages");
        this.__sending = new SynchedPropertySimpleOneWayPU(b3.sending, this, "sending");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(b3.darkMode, this, "darkMode");
        this.__input = new SynchedPropertySimpleTwoWayPU(b3.input, this, "input");
        this.onSend = () => { };
        this.setInitiallyProvidedValue(b3);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(z2: CounselorPage_Params) {
        if (z2.messages === undefined) {
            this.__messages.set([]);
        }
        if (z2.sending === undefined) {
            this.__sending.set(false);
        }
        if (z2.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (z2.onSend !== undefined) {
            this.onSend = z2.onSend;
        }
    }
    updateStateVars(y2: CounselorPage_Params) {
        this.__messages.reset(y2.messages);
        this.__sending.reset(y2.sending);
        this.__darkMode.reset(y2.darkMode);
    }
    purgeVariableDependenciesOnElmtId(x2) {
        this.__messages.purgeDependencyOnElmtId(x2);
        this.__sending.purgeDependencyOnElmtId(x2);
        this.__darkMode.purgeDependencyOnElmtId(x2);
        this.__input.purgeDependencyOnElmtId(x2);
    }
    aboutToBeDeleted() {
        this.__messages.aboutToBeDeleted();
        this.__sending.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__input.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __messages: SynchedPropertySimpleOneWayPU<ChatMessage[]>;
    get messages() {
        return this.__messages.get();
    }
    set messages(w2: ChatMessage[]) {
        this.__messages.set(w2);
    }
    private __sending: SynchedPropertySimpleOneWayPU<boolean>;
    get sending() {
        return this.__sending.get();
    }
    set sending(v2: boolean) {
        this.__sending.set(v2);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(u2: boolean) {
        this.__darkMode.set(u2);
    }
    private __input: SynchedPropertySimpleTwoWayPU<string>;
    get input() {
        return this.__input.get();
    }
    set input(t2: string) {
        this.__input.set(t2);
    }
    private onSend: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    MessageBubble(b2: ChatMessage, c2 = null) {
        this.observeComponentCreation2((r2, s2) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Bottom);
        }, Row);
        this.observeComponentCreation2((j2, k2) => {
            If.create();
            if (b2.role === 'assistant') {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((p2, q2) => {
                        Stack.create({ alignContent: Alignment.Center });
                        Stack.width(30);
                        Stack.height(30);
                        Stack.backgroundColor(this.palette().soft);
                        Stack.borderRadius(10);
                        Stack.margin({ right: 7 });
                    }, Stack);
                    this.observeComponentCreation2((n2, o2) => {
                        SymbolGlyph.create({ "id": 125833267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                    Stack.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((l2, m2) => {
                        Blank.create();
                        Blank.layoutWeight(1);
                    }, Blank);
                    Blank.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((h2, i2) => {
            Text.create(b2.content);
            Text.fontColor(b2.role === 'user' ? '#FFFFFFFF' : this.palette().text);
            Text.fontSize(13);
            Text.lineHeight(20);
            Text.padding({ left: 14, right: 14, top: 12, bottom: 12 });
            Text.backgroundColor(b2.role === 'user' ? this.palette().primary : this.palette().surface);
            Text.border({ width: b2.role === 'user' ? 0 : 1, color: this.palette().line });
            Text.borderRadius(19);
            Text.constraintSize({ maxWidth: '78%' });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((d2, e2) => {
            If.create();
            if (b2.role === 'assistant') {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((f2, g2) => {
                        Blank.create();
                        Blank.layoutWeight(1);
                    }, Blank);
                    Blank.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((z1, a2) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        this.observeComponentCreation2((x1, y1) => {
            Row.create();
            Row.width('100%');
            Row.padding({ left: 16, right: 16, top: 12, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((v1, w1) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((t1, u1) => {
            Text.create('AI 校园助手');
            Text.fontColor(this.palette().text);
            Text.fontSize(25);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r1, s1) => {
            Text.create('课程、通知与校园生活，随时问我');
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((p1, q1) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((n1, o1) => {
            Text.create('REAL');
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((l1, m1) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((j1, k1) => {
            Column.create({ space: 12 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, top: 8, bottom: 8 });
        }, Column);
        this.observeComponentCreation2((b1, c1) => {
            If.create();
            if (this.messages.length === 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.MessageBubble.bind(this)(makeBuilderParameterProxy("MessageBubble", { id: () => 'welcome', role: () => 'assistant', content: () => '你好，我是 CampusMate AI。课程、考试、校园服务或学习安排，都可以问我。' }));
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((d1, e1) => {
                        ForEach.create();
                        const f1 = h1 => {
                            const i1 = h1;
                            this.MessageBubble.bind(this)(i1);
                        };
                        this.forEachUpdateFunction(d1, this.messages, f1, (g1: ChatMessage) => g1.id, false, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((x, y) => {
            If.create();
            if (this.sending) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((z, a1) => {
                        LoadingProgress.create();
                        LoadingProgress.width(24);
                        LoadingProgress.height(24);
                        LoadingProgress.color(this.palette().primary);
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((v, w) => {
            Blank.create();
            Blank.height(12);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
        this.observeComponentCreation2((t, u) => {
            Column.create({ space: 6 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, top: 10, bottom: 104 });
            Column.backgroundColor(this.palette().surface);
        }, Column);
        this.observeComponentCreation2((r, s) => {
            Row.create({ space: 10 });
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((o, p) => {
            TextInput.create({ placeholder: '输入你的校园事务问题…', text: this.input });
            TextInput.layoutWeight(1);
            TextInput.height(48);
            TextInput.fontSize(13);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.backgroundColor(this.palette().surface);
            TextInput.border({ width: 1, color: this.palette().line });
            TextInput.borderRadius(18);
            TextInput.onChange((q: string) => this.input = q);
            TextInput.onSubmit(() => this.onSend());
        }, TextInput);
        this.observeComponentCreation2((m, n) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(48);
            Stack.height(48);
            Stack.backgroundColor(this.palette().primary);
            Stack.borderRadius(16);
            Stack.onClick(() => this.onSend());
        }, Stack);
        this.observeComponentCreation2((g, h) => {
            If.create();
            if (this.sending) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((k, l) => {
                        LoadingProgress.create();
                        LoadingProgress.width(20);
                        LoadingProgress.height(20);
                        LoadingProgress.color('#FFFFFFFF');
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((i, j) => {
                        SymbolGlyph.create({ "id": 125832671, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(20);
                        SymbolGlyph.fontColor(['#FFFFFFFF']);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Stack.pop();
        Row.pop();
        this.observeComponentCreation2((e, f) => {
            Row.create({ space: 4 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((c, d) => {
            SymbolGlyph.create({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((a, b) => {
            Text.create('仅提供校园事务辅助，不替代学校正式通知或专业咨询');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

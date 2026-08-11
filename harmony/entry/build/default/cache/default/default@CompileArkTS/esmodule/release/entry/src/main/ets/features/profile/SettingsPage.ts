if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface SettingsPage_Params {
    darkMode?: boolean;
    reduceMotion?: boolean;
    backendOnline?: boolean;
    onBack?: () => void;
    onThemeChange?: (value: boolean) => void;
    onMotionChange?: (value: boolean) => void;
    onNavigate?: (target: string) => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class SettingsPage extends ViewPU {
    constructor(j18, k18, l18, m18 = -1, n18 = undefined, o18) {
        super(j18, l18, m18, o18);
        if (typeof n18 === "function") {
            this.paramsGenerator_ = n18;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(k18.darkMode, this, "darkMode");
        this.__reduceMotion = new SynchedPropertySimpleOneWayPU(k18.reduceMotion, this, "reduceMotion");
        this.__backendOnline = new SynchedPropertySimpleOneWayPU(k18.backendOnline, this, "backendOnline");
        this.onBack = () => { };
        this.onThemeChange = () => { };
        this.onMotionChange = () => { };
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(k18);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(i18: SettingsPage_Params) {
        if (i18.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (i18.reduceMotion === undefined) {
            this.__reduceMotion.set(false);
        }
        if (i18.backendOnline === undefined) {
            this.__backendOnline.set(true);
        }
        if (i18.onBack !== undefined) {
            this.onBack = i18.onBack;
        }
        if (i18.onThemeChange !== undefined) {
            this.onThemeChange = i18.onThemeChange;
        }
        if (i18.onMotionChange !== undefined) {
            this.onMotionChange = i18.onMotionChange;
        }
        if (i18.onNavigate !== undefined) {
            this.onNavigate = i18.onNavigate;
        }
    }
    updateStateVars(h18: SettingsPage_Params) {
        this.__darkMode.reset(h18.darkMode);
        this.__reduceMotion.reset(h18.reduceMotion);
        this.__backendOnline.reset(h18.backendOnline);
    }
    purgeVariableDependenciesOnElmtId(g18) {
        this.__darkMode.purgeDependencyOnElmtId(g18);
        this.__reduceMotion.purgeDependencyOnElmtId(g18);
        this.__backendOnline.purgeDependencyOnElmtId(g18);
    }
    aboutToBeDeleted() {
        this.__darkMode.aboutToBeDeleted();
        this.__reduceMotion.aboutToBeDeleted();
        this.__backendOnline.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(f18: boolean) {
        this.__darkMode.set(f18);
    }
    private __reduceMotion: SynchedPropertySimpleOneWayPU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(e18: boolean) {
        this.__reduceMotion.set(e18);
    }
    private __backendOnline: SynchedPropertySimpleOneWayPU<boolean>;
    get backendOnline() {
        return this.__backendOnline.get();
    }
    set backendOnline(d18: boolean) {
        this.__backendOnline.set(d18);
    }
    private onBack: () => void;
    private onThemeChange: (value: boolean) => void;
    private onMotionChange: (value: boolean) => void;
    private onNavigate: (target: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    ToggleRow(j17: Resource, k17: string, l17: string, m17: boolean, n17: (value: boolean) => void, o17 = null) {
        this.observeComponentCreation2((b18, c18) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((z17, a18) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((x17, y17) => {
            SymbolGlyph.create(j17);
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((v17, w17) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((t17, u17) => {
            Text.create(k17);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r17, s17) => {
            Text.create(l17);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((p17, q17) => {
            Toggle.create({ type: ToggleType.Switch, isOn: m17 });
            Toggle.onChange(n17);
        }, Toggle);
        Toggle.pop();
        Row.pop();
    }
    LinkRow(q16: Resource, r16: string, s16: string, t16: string, u16 = null) {
        this.observeComponentCreation2((h17, i17) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
            Row.onClick(() => this.onNavigate(t16));
        }, Row);
        this.observeComponentCreation2((f17, g17) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((d17, e17) => {
            SymbolGlyph.create(q16);
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((b17, c17) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((z16, a17) => {
            Text.create(r16);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((x16, y16) => {
            Text.create(s16);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((v16, w16) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((o16, p16) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((k16, l16) => {
                if (l16) {
                    let m16 = new SecondaryHeader(this, { title: '系统设置', subtitle: '个性化你的校园助手', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, k16, () => { }, { page: "entry/src/main/ets/features/profile/SettingsPage.ets", line: 41, col: 7 });
                    ViewPU.create(m16);
                    let n16 = () => {
                        return {
                            title: '系统设置',
                            subtitle: '个性化你的校园助手',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    m16.paramsGenerator_ = n16;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(k16, {
                        title: '系统设置', subtitle: '个性化你的校园助手', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((i16, j16) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((g16, h16) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((e16, f16) => {
            Text.create('显示与动效');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((c16, d16) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.ToggleRow.bind(this)({ "id": 125831540, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '深色模式', this.darkMode ? '已使用夜间配色，减少暗处眩光' : '切换为更适合夜间的深色界面', this.darkMode, (b16: boolean) => this.onThemeChange(b16));
        this.observeComponentCreation2((z15, a16) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.ToggleRow.bind(this)({ "id": 125831581, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '减少动态效果', '减少页面进入与状态切换动画', this.reduceMotion, (y15: boolean) => this.onMotionChange(y15));
        Column.pop();
        this.observeComponentCreation2((w15, x15) => {
            Text.create('提醒与陪伴');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((u15, v15) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.LinkRow.bind(this)({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '截止提醒', '待办临近截止时发送系统通知', 'notifications');
        this.observeComponentCreation2((s15, t15) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.LinkRow.bind(this)({ "id": 125833267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'AI 与模型共建', '查看校园助手能力与隐私说明', 'about');
        Column.pop();
        this.observeComponentCreation2((q15, r15) => {
            Text.create('数据与服务');
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((o15, p15) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((m15, n15) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((k15, l15) => {
            SymbolGlyph.create({ "id": 125832515, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((i15, j15) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((g15, h15) => {
            Text.create('后端服务');
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((e15, f15) => {
            Text.create(this.backendOnline ? '已连接（real_backend）' : '暂未连接');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((c15, d15) => {
            Circle.create();
            Circle.width(9);
            Circle.height(9);
            Circle.fill(this.backendOnline ? this.palette().success : '#FFE35F42');
        }, Circle);
        Row.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

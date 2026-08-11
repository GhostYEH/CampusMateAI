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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__reduceMotion = new SynchedPropertySimpleOneWayPU(params.reduceMotion, this, "reduceMotion");
        this.__backendOnline = new SynchedPropertySimpleOneWayPU(params.backendOnline, this, "backendOnline");
        this.onBack = () => { };
        this.onThemeChange = () => { };
        this.onMotionChange = () => { };
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: SettingsPage_Params) {
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.reduceMotion === undefined) {
            this.__reduceMotion.set(false);
        }
        if (params.backendOnline === undefined) {
            this.__backendOnline.set(true);
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onThemeChange !== undefined) {
            this.onThemeChange = params.onThemeChange;
        }
        if (params.onMotionChange !== undefined) {
            this.onMotionChange = params.onMotionChange;
        }
        if (params.onNavigate !== undefined) {
            this.onNavigate = params.onNavigate;
        }
    }
    updateStateVars(params: SettingsPage_Params) {
        this.__darkMode.reset(params.darkMode);
        this.__reduceMotion.reset(params.reduceMotion);
        this.__backendOnline.reset(params.backendOnline);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__reduceMotion.purgeDependencyOnElmtId(rmElmtId);
        this.__backendOnline.purgeDependencyOnElmtId(rmElmtId);
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
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __reduceMotion: SynchedPropertySimpleOneWayPU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(newValue: boolean) {
        this.__reduceMotion.set(newValue);
    }
    private __backendOnline: SynchedPropertySimpleOneWayPU<boolean>;
    get backendOnline() {
        return this.__backendOnline.get();
    }
    set backendOnline(newValue: boolean) {
        this.__backendOnline.set(newValue);
    }
    private onBack: () => void;
    private onThemeChange: (value: boolean) => void;
    private onMotionChange: (value: boolean) => void;
    private onNavigate: (target: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    ToggleRow(symbol: Resource, title: string, subtitle: string, value: boolean, onChange: (value: boolean) => void, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(16:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(17:7)", "entry");
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(17:51)", "entry");
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(19:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(title);
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(20:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(subtitle);
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(21:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Toggle.create({ type: ToggleType.Switch, isOn: value });
            Toggle.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(23:7)", "entry");
            Toggle.onChange(onChange);
        }, Toggle);
        Toggle.pop();
        Row.pop();
    }
    LinkRow(symbol: Resource, title: string, subtitle: string, target: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(28:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
            Row.onClick(() => this.onNavigate(target));
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(29:7)", "entry");
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(29:51)", "entry");
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(31:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(title);
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(32:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(subtitle);
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(33:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(35:7)", "entry");
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(40:5)", "entry");
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: '系统设置', subtitle: '个性化你的校园助手', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/profile/SettingsPage.ets", line: 41, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: '系统设置',
                            subtitle: '个性化你的校园助手',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: '系统设置', subtitle: '个性化你的校园助手', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(42:7)", "entry");
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(43:9)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('显示与动效');
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(44:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(45:11)", "entry");
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.ToggleRow.bind(this)({ "id": 125831540, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '深色模式', this.darkMode ? '已使用夜间配色，减少暗处眩光' : '切换为更适合夜间的深色界面', this.darkMode, (value: boolean) => this.onThemeChange(value));
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(47:13)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.ToggleRow.bind(this)({ "id": 125831581, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '减少动态效果', '减少页面进入与状态切换动画', this.reduceMotion, (value: boolean) => this.onMotionChange(value));
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('提醒与陪伴');
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(50:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(51:11)", "entry");
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.LinkRow.bind(this)({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '截止提醒', '待办临近截止时发送系统通知', 'notifications');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(53:13)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.LinkRow.bind(this)({ "id": 125833267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'AI 与模型共建', '查看校园助手能力与隐私说明', 'about');
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('数据与服务');
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(56:11)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(57:11)", "entry");
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(18);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(58:13)", "entry");
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832515, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(58:57)", "entry");
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(60:13)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('后端服务');
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(61:15)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.backendOnline ? '已连接（real_backend）' : '暂未连接');
            Text.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(62:15)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Circle.create();
            Circle.debugLine("entry/src/main/ets/features/profile/SettingsPage.ets(64:13)", "entry");
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

if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface ProfilePage_Params {
    darkMode?: boolean;
    name?: string;
    detail?: string;
    onNavigate?: (route: string) => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
export class ProfilePage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__name = new SynchedPropertySimpleOneWayPU(params.name, this, "name");
        this.__detail = new SynchedPropertySimpleOneWayPU(params.detail, this, "detail");
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: ProfilePage_Params) {
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.name === undefined) {
            this.__name.set('林知夏');
        }
        if (params.detail === undefined) {
            this.__detail.set('计算机科学与技术 · 大三');
        }
        if (params.onNavigate !== undefined) {
            this.onNavigate = params.onNavigate;
        }
    }
    updateStateVars(params: ProfilePage_Params) {
        this.__darkMode.reset(params.darkMode);
        this.__name.reset(params.name);
        this.__detail.reset(params.detail);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__name.purgeDependencyOnElmtId(rmElmtId);
        this.__detail.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__darkMode.aboutToBeDeleted();
        this.__name.aboutToBeDeleted();
        this.__detail.aboutToBeDeleted();
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
    private __name: SynchedPropertySimpleOneWayPU<string>;
    get name() {
        return this.__name.get();
    }
    set name(newValue: string) {
        this.__name.set(newValue);
    }
    private __detail: SynchedPropertySimpleOneWayPU<string>;
    get detail() {
        return this.__detail.get();
    }
    set detail(newValue: string) {
        this.__detail.set(newValue);
    }
    private onNavigate: (route: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    QuickAction(label: string, symbol: Resource, route: string, accent: boolean, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 9 });
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(12:5)", "entry");
            Column.layoutWeight(1);
            Column.height('100%');
            Column.justifyContent(FlexAlign.Center);
            Column.onClick(() => this.onNavigate(route));
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(13:7)", "entry");
            Stack.width(43);
            Stack.height(43);
            Stack.backgroundColor(accent ? '#1FE08A4E' : this.palette().soft);
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(14:9)", "entry");
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor([accent ? this.palette().accent : this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(16:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        Column.pop();
    }
    MenuRow(label: string, symbol: Resource, route: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(21:5)", "entry");
            Row.width('100%');
            Row.height(70);
            Row.alignItems(VerticalAlign.Center);
            Row.onClick(() => this.onNavigate(route));
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(22:7)", "entry");
            SymbolGlyph.fontSize(27);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(23:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Medium);
            Text.layoutWeight(1);
            Text.margin({ left: 18 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(24:7)", "entry");
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(29:5)", "entry");
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 14 });
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(30:7)", "entry");
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.TopStart });
            Stack.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(31:9)", "entry");
            Stack.width('100%');
            Stack.height(382);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(32:11)", "entry");
            Column.width('100%');
            Column.height(318);
            Column.linearGradient({ angle: 90, colors: this.darkMode ? [['#FF17384A', 0], ['#FF2F6486', 1]] : [['#FF4E5EDB', 0], ['#FF6E79F5', 1]] });
            Column.borderRadius({ bottomLeft: 30, bottomRight: 30 });
        }, Column);
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(36:11)", "entry");
            Column.width('100%');
            Column.padding({ left: 24, top: 15, right: 20 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(37:13)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(38:15)", "entry");
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('我的');
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(39:17)", "entry");
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(28);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('今天也照顾好自己的节奏');
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(40:17)", "entry");
            Text.fontColor('#BDFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(42:15)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(43:15)", "entry");
            Stack.width(40);
            Stack.height(40);
            Stack.backgroundColor('#1FFFFFFF');
            Stack.borderRadius(20);
            Stack.onClick(() => this.onNavigate('settings'));
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831600, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(44:17)", "entry");
            SymbolGlyph.fontSize(22);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(47:13)", "entry");
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
            Row.margin({ top: 30 });
            Row.onClick(() => this.onNavigate('account'));
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777225, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(48:15)", "entry");
            Image.width(82);
            Image.height(82);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(41);
            Image.border({ width: 3, color: '#FFFFFFFF' });
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 7 });
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(50:15)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 17 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.name);
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(51:17)", "entry");
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.detail);
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(52:17)", "entry");
            Text.fontColor('#D6FFFFFF');
            Text.fontSize(14);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 4 });
            Row.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(53:17)", "entry");
            Row.padding({ left: 9, right: 9, top: 5, bottom: 5 });
            Row.backgroundColor('#1FFFFFFF');
            Row.borderRadius(13);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(54:19)", "entry");
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E0FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('资料已同步到当前账号');
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(55:19)", "entry");
            Text.fontColor('#E0FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(58:15)", "entry");
            SymbolGlyph.fontSize(22);
            SymbolGlyph.fontColor(['#CCFFFFFF']);
        }, SymbolGlyph);
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(61:11)", "entry");
            Row.width('100%');
            Row.height(126);
            Row.padding({ left: 7, right: 7, top: 16, bottom: 16 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(24);
            Row.position({ x: 16, y: 256 });
            Row.constraintSize({ maxWidth: '91%' });
        }, Row);
        this.QuickAction.bind(this)('文件', { "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'files', false);
        this.QuickAction.bind(this)('活动', { "id": 125832315, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'activities', true);
        this.QuickAction.bind(this)('收藏', { "id": 125831605, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'favorites', false);
        this.QuickAction.bind(this)('设置', { "id": 125831493, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'settings', false);
        Row.pop();
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('更多服务');
            Text.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(70:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
            Text.padding({ left: 20 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(71:9)", "entry");
            Column.width('100%');
            Column.padding({ left: 16, right: 16, top: 3, bottom: 3 });
            Column.backgroundColor(this.palette().surface);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(22);
        }, Column);
        this.MenuRow.bind(this)('学习与专注', { "id": 125832304, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'focus');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(72:67)", "entry");
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('通知与提醒', { "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'notifications');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(73:74)", "entry");
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('账号与隐私', { "id": 125832263, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'account');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(74:77)", "entry");
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('帮助与反馈', { "id": 125831766, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'counselor');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(75:73)", "entry");
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('关于 CampusMate', { "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'about');
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/profile/ProfilePage.ets(79:9)", "entry");
            Blank.height(102);
        }, Blank);
        Blank.pop();
        Column.pop();
        Scroll.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

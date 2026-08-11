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
    constructor(w14, x14, y14, z14 = -1, a15 = undefined, b15) {
        super(w14, y14, z14, b15);
        if (typeof a15 === "function") {
            this.paramsGenerator_ = a15;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(x14.darkMode, this, "darkMode");
        this.__name = new SynchedPropertySimpleOneWayPU(x14.name, this, "name");
        this.__detail = new SynchedPropertySimpleOneWayPU(x14.detail, this, "detail");
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(x14);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(v14: ProfilePage_Params) {
        if (v14.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (v14.name === undefined) {
            this.__name.set('林知夏');
        }
        if (v14.detail === undefined) {
            this.__detail.set('计算机科学与技术 · 大三');
        }
        if (v14.onNavigate !== undefined) {
            this.onNavigate = v14.onNavigate;
        }
    }
    updateStateVars(u14: ProfilePage_Params) {
        this.__darkMode.reset(u14.darkMode);
        this.__name.reset(u14.name);
        this.__detail.reset(u14.detail);
    }
    purgeVariableDependenciesOnElmtId(t14) {
        this.__darkMode.purgeDependencyOnElmtId(t14);
        this.__name.purgeDependencyOnElmtId(t14);
        this.__detail.purgeDependencyOnElmtId(t14);
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
    set darkMode(s14: boolean) {
        this.__darkMode.set(s14);
    }
    private __name: SynchedPropertySimpleOneWayPU<string>;
    get name() {
        return this.__name.get();
    }
    set name(r14: string) {
        this.__name.set(r14);
    }
    private __detail: SynchedPropertySimpleOneWayPU<string>;
    get detail() {
        return this.__detail.get();
    }
    set detail(q14: string) {
        this.__detail.set(q14);
    }
    private onNavigate: (route: string) => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    QuickAction(d14: string, e14: Resource, f14: string, g14: boolean, h14 = null) {
        this.observeComponentCreation2((o14, p14) => {
            Column.create({ space: 9 });
            Column.layoutWeight(1);
            Column.height('100%');
            Column.justifyContent(FlexAlign.Center);
            Column.onClick(() => this.onNavigate(f14));
        }, Column);
        this.observeComponentCreation2((m14, n14) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(43);
            Stack.height(43);
            Stack.backgroundColor(g14 ? '#1FE08A4E' : this.palette().soft);
            Stack.borderRadius(14);
        }, Stack);
        this.observeComponentCreation2((k14, l14) => {
            SymbolGlyph.create(e14);
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor([g14 ? this.palette().accent : this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((i14, j14) => {
            Text.create(d14);
            Text.fontColor(this.palette().text);
            Text.fontSize(12);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        Column.pop();
    }
    MenuRow(r13: string, s13: Resource, t13: string, u13 = null) {
        this.observeComponentCreation2((b14, c14) => {
            Row.create();
            Row.width('100%');
            Row.height(70);
            Row.alignItems(VerticalAlign.Center);
            Row.onClick(() => this.onNavigate(t13));
        }, Row);
        this.observeComponentCreation2((z13, a14) => {
            SymbolGlyph.create(s13);
            SymbolGlyph.fontSize(27);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((x13, y13) => {
            Text.create(r13);
            Text.fontColor(this.palette().text);
            Text.fontSize(16);
            Text.fontWeight(FontWeight.Medium);
            Text.layoutWeight(1);
            Text.margin({ left: 18 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((v13, w13) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((p13, q13) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
            Scroll.backgroundColor(this.palette().background);
        }, Scroll);
        this.observeComponentCreation2((n13, o13) => {
            Column.create({ space: 14 });
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((l13, m13) => {
            Stack.create({ alignContent: Alignment.TopStart });
            Stack.width('100%');
            Stack.height(382);
        }, Stack);
        this.observeComponentCreation2((j13, k13) => {
            Column.create();
            Column.width('100%');
            Column.height(318);
            Column.linearGradient({ angle: 90, colors: this.darkMode ? [['#FF17384A', 0], ['#FF2F6486', 1]] : [['#FF4E5EDB', 0], ['#FF6E79F5', 1]] });
            Column.borderRadius({ bottomLeft: 30, bottomRight: 30 });
        }, Column);
        Column.pop();
        this.observeComponentCreation2((h13, i13) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 24, top: 15, right: 20 });
        }, Column);
        this.observeComponentCreation2((f13, g13) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((d13, e13) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((b13, c13) => {
            Text.create('我的');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(28);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((z12, a13) => {
            Text.create('今天也照顾好自己的节奏');
            Text.fontColor('#BDFFFFFF');
            Text.fontSize(11);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((x12, y12) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((v12, w12) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.backgroundColor('#1FFFFFFF');
            Stack.borderRadius(20);
            Stack.onClick(() => this.onNavigate('settings'));
        }, Stack);
        this.observeComponentCreation2((t12, u12) => {
            SymbolGlyph.create({ "id": 125831600, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(22);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        Row.pop();
        this.observeComponentCreation2((r12, s12) => {
            Row.create();
            Row.width('100%');
            Row.alignItems(VerticalAlign.Center);
            Row.margin({ top: 30 });
            Row.onClick(() => this.onNavigate('account'));
        }, Row);
        this.observeComponentCreation2((p12, q12) => {
            Image.create({ "id": 16777224, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width(82);
            Image.height(82);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(41);
            Image.border({ width: 3, color: '#FFFFFFFF' });
        }, Image);
        this.observeComponentCreation2((n12, o12) => {
            Column.create({ space: 7 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 17 });
        }, Column);
        this.observeComponentCreation2((l12, m12) => {
            Text.create(this.name);
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(24);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j12, k12) => {
            Text.create(this.detail);
            Text.fontColor('#D6FFFFFF');
            Text.fontSize(14);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h12, i12) => {
            Row.create({ space: 4 });
            Row.padding({ left: 9, right: 9, top: 5, bottom: 5 });
            Row.backgroundColor('#1FFFFFFF');
            Row.borderRadius(13);
        }, Row);
        this.observeComponentCreation2((f12, g12) => {
            SymbolGlyph.create({ "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(11);
            SymbolGlyph.fontColor(['#E0FFFFFF']);
        }, SymbolGlyph);
        this.observeComponentCreation2((d12, e12) => {
            Text.create('资料已同步到当前账号');
            Text.fontColor('#E0FFFFFF');
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((b12, c12) => {
            SymbolGlyph.create({ "id": 125832664, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(22);
            SymbolGlyph.fontColor(['#CCFFFFFF']);
        }, SymbolGlyph);
        Row.pop();
        Column.pop();
        this.observeComponentCreation2((z11, a12) => {
            Row.create();
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
        this.observeComponentCreation2((x11, y11) => {
            Text.create('更多服务');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
            Text.padding({ left: 20 });
        }, Text);
        Text.pop();
        this.observeComponentCreation2((v11, w11) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 16, right: 16, top: 3, bottom: 3 });
            Column.backgroundColor(this.palette().surface);
            Column.border({ width: 1, color: this.palette().line });
            Column.borderRadius(22);
        }, Column);
        this.MenuRow.bind(this)('学习与专注', { "id": 125832304, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'focus');
        this.observeComponentCreation2((t11, u11) => {
            Divider.create();
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('通知与提醒', { "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'notifications');
        this.observeComponentCreation2((r11, s11) => {
            Divider.create();
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('账号与隐私', { "id": 125832263, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'account');
        this.observeComponentCreation2((p11, q11) => {
            Divider.create();
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('帮助与反馈', { "id": 125831766, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'counselor');
        this.observeComponentCreation2((n11, o11) => {
            Divider.create();
            Divider.color(this.palette().line);
            Divider.margin({ left: 53 });
        }, Divider);
        this.MenuRow.bind(this)('关于 CampusMate', { "id": 125832646, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, 'about');
        Column.pop();
        this.observeComponentCreation2((l11, m11) => {
            Blank.create();
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

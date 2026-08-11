if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface AccountPage_Params {
    darkMode?: boolean;
    name?: string;
    detail?: string;
    onBack?: () => void;
    onSignOut?: () => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class AccountPage extends ViewPU {
    constructor(t5, u5, v5, w5 = -1, x5 = undefined, y5) {
        super(t5, v5, w5, y5);
        if (typeof x5 === "function") {
            this.paramsGenerator_ = x5;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(u5.darkMode, this, "darkMode");
        this.__name = new SynchedPropertySimpleOneWayPU(u5.name, this, "name");
        this.__detail = new SynchedPropertySimpleOneWayPU(u5.detail, this, "detail");
        this.onBack = () => { };
        this.onSignOut = () => { };
        this.setInitiallyProvidedValue(u5);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(s5: AccountPage_Params) {
        if (s5.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (s5.name === undefined) {
            this.__name.set('');
        }
        if (s5.detail === undefined) {
            this.__detail.set('');
        }
        if (s5.onBack !== undefined) {
            this.onBack = s5.onBack;
        }
        if (s5.onSignOut !== undefined) {
            this.onSignOut = s5.onSignOut;
        }
    }
    updateStateVars(r5: AccountPage_Params) {
        this.__darkMode.reset(r5.darkMode);
        this.__name.reset(r5.name);
        this.__detail.reset(r5.detail);
    }
    purgeVariableDependenciesOnElmtId(q5) {
        this.__darkMode.purgeDependencyOnElmtId(q5);
        this.__name.purgeDependencyOnElmtId(q5);
        this.__detail.purgeDependencyOnElmtId(q5);
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
    set darkMode(p5: boolean) {
        this.__darkMode.set(p5);
    }
    private __name: SynchedPropertySimpleOneWayPU<string>;
    get name() {
        return this.__name.get();
    }
    set name(o5: string) {
        this.__name.set(o5);
    }
    private __detail: SynchedPropertySimpleOneWayPU<string>;
    get detail() {
        return this.__detail.get();
    }
    set detail(n5: string) {
        this.__detail.set(n5);
    }
    private onBack: () => void;
    private onSignOut: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    InfoRow(c5: string, d5: string, e5 = null) {
        this.observeComponentCreation2((l5, m5) => {
            Row.create();
            Row.width('100%');
            Row.padding({ top: 14, bottom: 14 });
        }, Row);
        this.observeComponentCreation2((j5, k5) => {
            Text.create(c5);
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h5, i5) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((f5, g5) => {
            Text.create(d5);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Medium);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((a5, b5) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((w4, x4) => {
                if (x4) {
                    let y4 = new SecondaryHeader(this, { title: '账号与隐私', subtitle: '个人资料和账号信息', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, w4, () => { }, { page: "entry/src/main/ets/features/profile/AccountPage.ets", line: 23, col: 7 });
                    ViewPU.create(y4);
                    let z4 = () => {
                        return {
                            title: '账号与隐私',
                            subtitle: '个人资料和账号信息',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    y4.paramsGenerator_ = z4;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(w4, {
                        title: '账号与隐私', subtitle: '个人资料和账号信息', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((u4, v4) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((s4, t4) => {
            Column.create({ space: 14 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((q4, r4) => {
            Column.create({ space: 10 });
            Column.width('100%');
            Column.padding({ top: 22, bottom: 20 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
        }, Column);
        this.observeComponentCreation2((o4, p4) => {
            Image.create({ "id": 16777224, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width(86);
            Image.height(86);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(43);
        }, Image);
        this.observeComponentCreation2((m4, n4) => {
            Text.create(this.name);
            Text.fontColor(this.palette().text);
            Text.fontSize(21);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((k4, l4) => {
            Text.create(this.detail);
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((i4, j4) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 15, right: 15 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.InfoRow.bind(this)('登录账号', this.name);
        this.observeComponentCreation2((g4, h4) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.InfoRow.bind(this)('身份信息', this.detail);
        this.observeComponentCreation2((e4, f4) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.InfoRow.bind(this)('数据同步', '已连接当前账号');
        Column.pop();
        this.observeComponentCreation2((c4, d4) => {
            Row.create({ space: 9 });
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(15);
        }, Row);
        this.observeComponentCreation2((a4, b4) => {
            SymbolGlyph.create({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        this.observeComponentCreation2((y3, z3) => {
            Text.create('密码和令牌不会在界面中明文显示');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((w3, x3) => {
            Button.createWithLabel('退出当前账号');
            Button.width('100%');
            Button.height(50);
            Button.backgroundColor('#FFFFECEA');
            Button.fontColor('#FFC25450');
            Button.onClick(() => this.onSignOut());
        }, Button);
        Button.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

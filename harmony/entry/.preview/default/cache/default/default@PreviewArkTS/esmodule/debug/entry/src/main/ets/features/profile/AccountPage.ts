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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__name = new SynchedPropertySimpleOneWayPU(params.name, this, "name");
        this.__detail = new SynchedPropertySimpleOneWayPU(params.detail, this, "detail");
        this.onBack = () => { };
        this.onSignOut = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: AccountPage_Params) {
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.name === undefined) {
            this.__name.set('');
        }
        if (params.detail === undefined) {
            this.__detail.set('');
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onSignOut !== undefined) {
            this.onSignOut = params.onSignOut;
        }
    }
    updateStateVars(params: AccountPage_Params) {
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
    private onBack: () => void;
    private onSignOut: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    InfoRow(label: string, value: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(14:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 14, bottom: 14 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(15:7)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(16:7)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(value);
            Text.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(17:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Medium);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(22:5)", "entry");
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: '账号与隐私', subtitle: '个人资料和账号信息', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/profile/AccountPage.ets", line: 23, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: '账号与隐私',
                            subtitle: '个人资料和账号信息',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: '账号与隐私', subtitle: '个人资料和账号信息', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(24:7)", "entry");
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 14 });
            Column.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(25:9)", "entry");
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 10 });
            Column.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(26:11)", "entry");
            Column.width('100%');
            Column.padding({ top: 22, bottom: 20 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(20);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777225, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(27:13)", "entry");
            Image.width(86);
            Image.height(86);
            Image.objectFit(ImageFit.Cover);
            Image.borderRadius(43);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.name);
            Text.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(28:13)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(21);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.detail);
            Text.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(29:13)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(12);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(31:11)", "entry");
            Column.width('100%');
            Column.padding({ left: 15, right: 15 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.InfoRow.bind(this)('登录账号', this.name);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(33:13)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.InfoRow.bind(this)('身份信息', this.detail);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(35:13)", "entry");
            Divider.color(this.palette().line);
        }, Divider);
        this.InfoRow.bind(this)('数据同步', '已连接当前账号');
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 9 });
            Row.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(38:11)", "entry");
            Row.width('100%');
            Row.padding(13);
            Row.backgroundColor(this.palette().surface);
            Row.borderRadius(15);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(39:13)", "entry");
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([this.palette().success]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('密码和令牌不会在界面中明文显示');
            Text.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(40:13)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Button.createWithLabel('退出当前账号');
            Button.debugLine("entry/src/main/ets/features/profile/AccountPage.ets(42:11)", "entry");
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

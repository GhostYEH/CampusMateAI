if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface LoginScreen_Params {
    username?: string;
    password?: string;
    loading?: boolean;
    error?: string;
    reduceMotion?: boolean;
    onSubmit?: () => void;
    onInputChanged?: () => void;
    showPassword?: boolean;
    usernameFocused?: boolean;
    passwordFocused?: boolean;
    videoController?: VideoController;
}
const LOGIN_INK: string = '#111A31';
const LOGIN_BLUE_DEEP: string = '#3E50D9';
const LOGIN_WARM: string = '#FFA45B';
const FORM_TEXT: string = '#F8FAFF';
const FORM_MUTED: string = '#BDEBF0FF';
export class LoginScreen extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__username = new SynchedPropertySimpleTwoWayPU(params.username, this, "username");
        this.__password = new SynchedPropertySimpleTwoWayPU(params.password, this, "password");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__error = new SynchedPropertySimpleOneWayPU(params.error, this, "error");
        this.__reduceMotion = new SynchedPropertySimpleOneWayPU(params.reduceMotion, this, "reduceMotion");
        this.onSubmit = () => { };
        this.onInputChanged = () => { };
        this.__showPassword = new ObservedPropertySimplePU(false, this, "showPassword");
        this.__usernameFocused = new ObservedPropertySimplePU(false, this, "usernameFocused");
        this.__passwordFocused = new ObservedPropertySimplePU(false, this, "passwordFocused");
        this.videoController = new VideoController();
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: LoginScreen_Params) {
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.error === undefined) {
            this.__error.set('');
        }
        if (params.reduceMotion === undefined) {
            this.__reduceMotion.set(false);
        }
        if (params.onSubmit !== undefined) {
            this.onSubmit = params.onSubmit;
        }
        if (params.onInputChanged !== undefined) {
            this.onInputChanged = params.onInputChanged;
        }
        if (params.showPassword !== undefined) {
            this.showPassword = params.showPassword;
        }
        if (params.usernameFocused !== undefined) {
            this.usernameFocused = params.usernameFocused;
        }
        if (params.passwordFocused !== undefined) {
            this.passwordFocused = params.passwordFocused;
        }
        if (params.videoController !== undefined) {
            this.videoController = params.videoController;
        }
    }
    updateStateVars(params: LoginScreen_Params) {
        this.__loading.reset(params.loading);
        this.__error.reset(params.error);
        this.__reduceMotion.reset(params.reduceMotion);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__username.purgeDependencyOnElmtId(rmElmtId);
        this.__password.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__error.purgeDependencyOnElmtId(rmElmtId);
        this.__reduceMotion.purgeDependencyOnElmtId(rmElmtId);
        this.__showPassword.purgeDependencyOnElmtId(rmElmtId);
        this.__usernameFocused.purgeDependencyOnElmtId(rmElmtId);
        this.__passwordFocused.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__username.aboutToBeDeleted();
        this.__password.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__error.aboutToBeDeleted();
        this.__reduceMotion.aboutToBeDeleted();
        this.__showPassword.aboutToBeDeleted();
        this.__usernameFocused.aboutToBeDeleted();
        this.__passwordFocused.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __username: SynchedPropertySimpleTwoWayPU<string>;
    get username() {
        return this.__username.get();
    }
    set username(newValue: string) {
        this.__username.set(newValue);
    }
    private __password: SynchedPropertySimpleTwoWayPU<string>;
    get password() {
        return this.__password.get();
    }
    set password(newValue: string) {
        this.__password.set(newValue);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(newValue: boolean) {
        this.__loading.set(newValue);
    }
    private __error: SynchedPropertySimpleOneWayPU<string>;
    get error() {
        return this.__error.get();
    }
    set error(newValue: string) {
        this.__error.set(newValue);
    }
    private __reduceMotion: SynchedPropertySimpleOneWayPU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(newValue: boolean) {
        this.__reduceMotion.set(newValue);
    }
    private onSubmit: () => void;
    private onInputChanged: () => void;
    private __showPassword: ObservedPropertySimplePU<boolean>;
    get showPassword() {
        return this.__showPassword.get();
    }
    set showPassword(newValue: boolean) {
        this.__showPassword.set(newValue);
    }
    private __usernameFocused: ObservedPropertySimplePU<boolean>;
    get usernameFocused() {
        return this.__usernameFocused.get();
    }
    set usernameFocused(newValue: boolean) {
        this.__usernameFocused.set(newValue);
    }
    private __passwordFocused: ObservedPropertySimplePU<boolean>;
    get passwordFocused() {
        return this.__passwordFocused.get();
    }
    set passwordFocused(newValue: boolean) {
        this.__passwordFocused.set(newValue);
    }
    private videoController: VideoController;
    aboutToDisappear(): void {
        this.videoController.stop();
    }
    LoginBrand(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.borderRadius(13);
            Stack.backgroundColor(LOGIN_WARM);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125834958, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 10 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('CampusMate AI');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('校园事务 · 温和陪伴');
            Text.fontColor('#B3FFFFFF');
            Text.fontSize(9.5);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    LoginField(label: string, placeholder: string, symbol: Resource, isPassword: boolean, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 6 });
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(label);
            Text.fontColor(FORM_MUTED);
            Text.fontSize(11);
            Text.fontWeight(FontWeight.Medium);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.height(45);
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([FORM_MUTED]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({
                placeholder: placeholder,
                text: isPassword ? this.password : this.username
            });
            TextInput.layoutWeight(1);
            TextInput.height(44);
            TextInput.fontSize(14);
            TextInput.fontColor(FORM_TEXT);
            TextInput.placeholderFont({ size: 13 });
            TextInput.placeholderColor('#75FFFFFF');
            TextInput.caretColor('#FFFFFFFF');
            TextInput.backgroundColor(Color.Transparent);
            TextInput.border({ width: 0 });
            TextInput.padding(0);
            TextInput.type(isPassword && !this.showPassword ? InputType.Password : InputType.Normal);
            TextInput.showPasswordIcon(false);
            TextInput.enterKeyType(isPassword ? EnterKeyType.Done : EnterKeyType.Next);
            TextInput.onFocus(() => {
                if (isPassword) {
                    this.passwordFocused = true;
                }
                else {
                    this.usernameFocused = true;
                }
            });
            TextInput.onBlur(() => {
                if (isPassword) {
                    this.passwordFocused = false;
                }
                else {
                    this.usernameFocused = false;
                }
            });
            TextInput.onChange((value: string) => {
                if (isPassword) {
                    this.password = value;
                }
                else {
                    this.username = value;
                }
                this.onInputChanged();
            });
            TextInput.onSubmit(() => {
                if (isPassword) {
                    this.onSubmit();
                }
            });
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (isPassword) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create(this.showPassword ? { "id": 125832272, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" } : { "id": 125832271, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(20);
                        SymbolGlyph.fontColor([FORM_MUTED]);
                        SymbolGlyph.width(28);
                        SymbolGlyph.height(44);
                        SymbolGlyph.onClick(() => {
                            this.showPassword = !this.showPassword;
                        });
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.strokeWidth(1);
            Divider.color((isPassword ? this.passwordFocused : this.usernameFocused) ? '#FFFFFFFF' : '#52FFFFFF');
        }, Divider);
        Column.pop();
    }
    LoginContent(parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.alignItems(HorizontalAlign.Start);
            Column.padding({ left: 24, top: 20, right: 24 });
        }, Column);
        this.LoginBrand.bind(this)();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.height(66);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('欢迎回到校园');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(32);
            Text.fontWeight(FontWeight.Bold);
            Text.letterSpacing(-0.5);
            Text.lineHeight(38);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.height(8);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('课程、通知与每一个重要截止，\n都替你稳稳记着。');
            Text.fontColor('#D1FFFFFF');
            Text.fontSize(13);
            Text.lineHeight(20);
            Text.width('100%');
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.height(42);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 16 });
            Column.width('100%');
            Column.alignItems(HorizontalAlign.Start);
            Column.padding({ left: 24, top: 18, right: 24, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('登录 CampusMate');
            Text.fontColor(FORM_TEXT);
            Text.fontSize(23);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('使用学校统一身份账号继续。');
            Text.fontColor(FORM_MUTED);
            Text.fontSize(11.5);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.LoginField.bind(this)('账号', '学号 / 工号 / 用户名', { "id": 125832135, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, false);
        this.LoginField.bind(this)('密码', '请输入密码', { "id": 125832252, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, true);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.error.length > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create(this.error);
                        Text.fontColor('#FFFFC5BF');
                        Text.fontSize(11.5);
                        Text.width('100%');
                        Text.padding({ left: 12, right: 12, top: 9, bottom: 9 });
                        Text.backgroundColor('#663E171A');
                        Text.borderRadius(10);
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
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.width('100%');
            Row.height(51);
            Row.justifyContent(FlexAlign.Center);
            Row.alignItems(VerticalAlign.Center);
            Row.backgroundColor('#FFFFFFFF');
            Row.borderRadius(14);
            Row.opacity(this.loading ? 0.82 : 1.0);
            Row.onClick(() => {
                if (!this.loading) {
                    this.onSubmit();
                }
            });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.width(18);
                        LoadingProgress.height(18);
                        LoadingProgress.color(LOGIN_BLUE_DEEP);
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create('进入校园空间');
                        Text.fontColor(LOGIN_BLUE_DEEP);
                        Text.fontSize(14);
                        Text.fontWeight(FontWeight.Bold);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125832680, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor([LOGIN_BLUE_DEEP]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('登录即表示你已阅读并同意校园数据使用说明');
            Text.fontColor('#7AFFFFFF');
            Text.fontSize(9.5);
            Text.width('100%');
            Text.textAlign(TextAlign.Center);
        }, Text);
        Text.pop();
        Column.pop();
        Column.pop();
        Scroll.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create();
            Stack.width('100%');
            Stack.height('100%');
            Stack.backgroundColor(LOGIN_INK);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Image.create({ "id": 16777222, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height('100%');
            Image.objectFit(ImageFit.Cover);
            Image.expandSafeArea([SafeAreaType.SYSTEM], [SafeAreaEdge.TOP, SafeAreaEdge.BOTTOM]);
        }, Image);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (!this.reduceMotion) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Video.create({
                            src: { "id": 16777223, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" },
                            previewUri: { "id": 16777222, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" },
                            controller: this.videoController
                        });
                        Video.width('100%');
                        Video.height('100%');
                        Video.objectFit(ImageFit.Cover);
                        Video.autoPlay(true);
                        Video.muted(true);
                        Video.controls(false);
                        Video.loop(true);
                        Video.expandSafeArea([SafeAreaType.SYSTEM], [SafeAreaEdge.TOP, SafeAreaEdge.BOTTOM]);
                    }, Video);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.linearGradient({
                angle: 180,
                colors: [
                    ['#5C091632', 0.0],
                    ['#52091632', 0.38],
                    ['#C4091632', 0.68],
                    ['#F0091632', 1.0]
                ]
            });
            Column.expandSafeArea([SafeAreaType.SYSTEM], [SafeAreaEdge.TOP, SafeAreaEdge.BOTTOM]);
        }, Column);
        Column.pop();
        this.LoginContent.bind(this)();
        Stack.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

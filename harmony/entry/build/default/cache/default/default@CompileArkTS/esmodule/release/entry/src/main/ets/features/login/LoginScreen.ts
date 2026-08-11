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
    constructor(x11, y11, z11, a12 = -1, b12 = undefined, c12) {
        super(x11, z11, a12, c12);
        if (typeof b12 === "function") {
            this.paramsGenerator_ = b12;
        }
        this.__username = new SynchedPropertySimpleTwoWayPU(y11.username, this, "username");
        this.__password = new SynchedPropertySimpleTwoWayPU(y11.password, this, "password");
        this.__loading = new SynchedPropertySimpleOneWayPU(y11.loading, this, "loading");
        this.__error = new SynchedPropertySimpleOneWayPU(y11.error, this, "error");
        this.__reduceMotion = new SynchedPropertySimpleOneWayPU(y11.reduceMotion, this, "reduceMotion");
        this.onSubmit = () => { };
        this.onInputChanged = () => { };
        this.__showPassword = new ObservedPropertySimplePU(false, this, "showPassword");
        this.__usernameFocused = new ObservedPropertySimplePU(false, this, "usernameFocused");
        this.__passwordFocused = new ObservedPropertySimplePU(false, this, "passwordFocused");
        this.videoController = new VideoController();
        this.setInitiallyProvidedValue(y11);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(w11: LoginScreen_Params) {
        if (w11.loading === undefined) {
            this.__loading.set(false);
        }
        if (w11.error === undefined) {
            this.__error.set('');
        }
        if (w11.reduceMotion === undefined) {
            this.__reduceMotion.set(false);
        }
        if (w11.onSubmit !== undefined) {
            this.onSubmit = w11.onSubmit;
        }
        if (w11.onInputChanged !== undefined) {
            this.onInputChanged = w11.onInputChanged;
        }
        if (w11.showPassword !== undefined) {
            this.showPassword = w11.showPassword;
        }
        if (w11.usernameFocused !== undefined) {
            this.usernameFocused = w11.usernameFocused;
        }
        if (w11.passwordFocused !== undefined) {
            this.passwordFocused = w11.passwordFocused;
        }
        if (w11.videoController !== undefined) {
            this.videoController = w11.videoController;
        }
    }
    updateStateVars(v11: LoginScreen_Params) {
        this.__loading.reset(v11.loading);
        this.__error.reset(v11.error);
        this.__reduceMotion.reset(v11.reduceMotion);
    }
    purgeVariableDependenciesOnElmtId(u11) {
        this.__username.purgeDependencyOnElmtId(u11);
        this.__password.purgeDependencyOnElmtId(u11);
        this.__loading.purgeDependencyOnElmtId(u11);
        this.__error.purgeDependencyOnElmtId(u11);
        this.__reduceMotion.purgeDependencyOnElmtId(u11);
        this.__showPassword.purgeDependencyOnElmtId(u11);
        this.__usernameFocused.purgeDependencyOnElmtId(u11);
        this.__passwordFocused.purgeDependencyOnElmtId(u11);
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
    set username(t11: string) {
        this.__username.set(t11);
    }
    private __password: SynchedPropertySimpleTwoWayPU<string>;
    get password() {
        return this.__password.get();
    }
    set password(s11: string) {
        this.__password.set(s11);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(r11: boolean) {
        this.__loading.set(r11);
    }
    private __error: SynchedPropertySimpleOneWayPU<string>;
    get error() {
        return this.__error.get();
    }
    set error(q11: string) {
        this.__error.set(q11);
    }
    private __reduceMotion: SynchedPropertySimpleOneWayPU<boolean>;
    get reduceMotion() {
        return this.__reduceMotion.get();
    }
    set reduceMotion(p11: boolean) {
        this.__reduceMotion.set(p11);
    }
    private onSubmit: () => void;
    private onInputChanged: () => void;
    private __showPassword: ObservedPropertySimplePU<boolean>;
    get showPassword() {
        return this.__showPassword.get();
    }
    set showPassword(o11: boolean) {
        this.__showPassword.set(o11);
    }
    private __usernameFocused: ObservedPropertySimplePU<boolean>;
    get usernameFocused() {
        return this.__usernameFocused.get();
    }
    set usernameFocused(n11: boolean) {
        this.__usernameFocused.set(n11);
    }
    private __passwordFocused: ObservedPropertySimplePU<boolean>;
    get passwordFocused() {
        return this.__passwordFocused.get();
    }
    set passwordFocused(m11: boolean) {
        this.__passwordFocused.set(m11);
    }
    private videoController: VideoController;
    aboutToDisappear(): void {
        this.videoController.stop();
    }
    LoginBrand(z10 = null) {
        this.observeComponentCreation2((k11, l11) => {
            Row.create();
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((i11, j11) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.borderRadius(13);
            Stack.backgroundColor(LOGIN_WARM);
        }, Stack);
        this.observeComponentCreation2((g11, h11) => {
            SymbolGlyph.create({ "id": 125834958, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(23);
            SymbolGlyph.fontColor(['#FFFFFFFF']);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((e11, f11) => {
            Column.create({ space: 2 });
            Column.alignItems(HorizontalAlign.Start);
            Column.margin({ left: 10 });
        }, Column);
        this.observeComponentCreation2((c11, d11) => {
            Text.create('CampusMate AI');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(14);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((a11, b11) => {
            Text.create('校园事务 · 温和陪伴');
            Text.fontColor('#B3FFFFFF');
            Text.fontSize(9.5);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    LoginField(d10: string, e10: string, f10: Resource, g10: boolean, h10 = null) {
        this.observeComponentCreation2((x10, y10) => {
            Column.create({ space: 6 });
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((v10, w10) => {
            Text.create(d10);
            Text.fontColor(FORM_MUTED);
            Text.fontSize(11);
            Text.fontWeight(FontWeight.Medium);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t10, u10) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.height(45);
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((r10, s10) => {
            SymbolGlyph.create(f10);
            SymbolGlyph.fontSize(18);
            SymbolGlyph.fontColor([FORM_MUTED]);
        }, SymbolGlyph);
        this.observeComponentCreation2((o10, p10) => {
            TextInput.create({
                placeholder: e10,
                text: g10 ? this.password : this.username
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
            TextInput.type(g10 && !this.showPassword ? InputType.Password : InputType.Normal);
            TextInput.showPasswordIcon(false);
            TextInput.enterKeyType(g10 ? EnterKeyType.Done : EnterKeyType.Next);
            TextInput.onFocus(() => {
                if (g10) {
                    this.passwordFocused = true;
                }
                else {
                    this.usernameFocused = true;
                }
            });
            TextInput.onBlur(() => {
                if (g10) {
                    this.passwordFocused = false;
                }
                else {
                    this.usernameFocused = false;
                }
            });
            TextInput.onChange((q10: string) => {
                if (g10) {
                    this.password = q10;
                }
                else {
                    this.username = q10;
                }
                this.onInputChanged();
            });
            TextInput.onSubmit(() => {
                if (g10) {
                    this.onSubmit();
                }
            });
        }, TextInput);
        this.observeComponentCreation2((k10, l10) => {
            If.create();
            if (g10) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((m10, n10) => {
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
        this.observeComponentCreation2((i10, j10) => {
            Divider.create();
            Divider.strokeWidth(1);
            Divider.color((g10 ? this.passwordFocused : this.usernameFocused) ? '#FFFFFFFF' : '#52FFFFFF');
        }, Divider);
        Column.pop();
    }
    LoginContent(q8 = null) {
        this.observeComponentCreation2((b10, c10) => {
            Scroll.create();
            Scroll.width('100%');
            Scroll.height('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((z9, a10) => {
            Column.create();
            Column.width('100%');
        }, Column);
        this.observeComponentCreation2((x9, y9) => {
            Column.create();
            Column.width('100%');
            Column.alignItems(HorizontalAlign.Start);
            Column.padding({ left: 24, top: 20, right: 24 });
        }, Column);
        this.LoginBrand.bind(this)();
        this.observeComponentCreation2((v9, w9) => {
            Blank.create();
            Blank.height(66);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((t9, u9) => {
            Text.create('欢迎回到校园');
            Text.fontColor('#FFFFFFFF');
            Text.fontSize(32);
            Text.fontWeight(FontWeight.Bold);
            Text.letterSpacing(-0.5);
            Text.lineHeight(38);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r9, s9) => {
            Blank.create();
            Blank.height(8);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((p9, q9) => {
            Text.create('课程、通知与每一个重要截止，\n都替你稳稳记着。');
            Text.fontColor('#D1FFFFFF');
            Text.fontSize(13);
            Text.lineHeight(20);
            Text.width('100%');
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((n9, o9) => {
            Blank.create();
            Blank.height(42);
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((l9, m9) => {
            Column.create({ space: 16 });
            Column.width('100%');
            Column.alignItems(HorizontalAlign.Start);
            Column.padding({ left: 24, top: 18, right: 24, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((j9, k9) => {
            Text.create('登录 CampusMate');
            Text.fontColor(FORM_TEXT);
            Text.fontSize(23);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h9, i9) => {
            Text.create('使用学校统一身份账号继续。');
            Text.fontColor(FORM_MUTED);
            Text.fontSize(11.5);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.LoginField.bind(this)('账号', '学号 / 工号 / 用户名', { "id": 125832135, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, false);
        this.LoginField.bind(this)('密码', '请输入密码', { "id": 125832252, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, true);
        this.observeComponentCreation2((d9, e9) => {
            If.create();
            if (this.error.length > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((f9, g9) => {
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
        this.observeComponentCreation2((b9, c9) => {
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
        this.observeComponentCreation2((t8, u8) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((z8, a9) => {
                        LoadingProgress.create();
                        LoadingProgress.width(18);
                        LoadingProgress.height(18);
                        LoadingProgress.color(LOGIN_BLUE_DEEP);
                    }, LoadingProgress);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((x8, y8) => {
                        Text.create('进入校园空间');
                        Text.fontColor(LOGIN_BLUE_DEEP);
                        Text.fontSize(14);
                        Text.fontWeight(FontWeight.Bold);
                    }, Text);
                    Text.pop();
                    this.observeComponentCreation2((v8, w8) => {
                        SymbolGlyph.create({ "id": 125832680, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(17);
                        SymbolGlyph.fontColor([LOGIN_BLUE_DEEP]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Row.pop();
        this.observeComponentCreation2((r8, s8) => {
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
        this.observeComponentCreation2((o8, p8) => {
            Stack.create();
            Stack.width('100%');
            Stack.height('100%');
            Stack.backgroundColor(LOGIN_INK);
        }, Stack);
        this.observeComponentCreation2((m8, n8) => {
            Image.create({ "id": 16777222, "type": 20000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            Image.width('100%');
            Image.height('100%');
            Image.objectFit(ImageFit.Cover);
            Image.expandSafeArea([SafeAreaType.SYSTEM], [SafeAreaEdge.TOP, SafeAreaEdge.BOTTOM]);
        }, Image);
        this.observeComponentCreation2((i8, j8) => {
            If.create();
            if (!this.reduceMotion) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((k8, l8) => {
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
        this.observeComponentCreation2((g8, h8) => {
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

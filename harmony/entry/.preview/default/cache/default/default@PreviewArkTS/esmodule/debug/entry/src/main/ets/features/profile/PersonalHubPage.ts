if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface PersonalHubPage_Params {
    section?: string;
    files?: PersonalFileItem[];
    activities?: ActivityItem[];
    favorites?: FavoriteItem[];
    loading?: boolean;
    darkMode?: boolean;
    query?: string;
    onBack?: () => void;
    onRefresh?: () => void;
}
import type { ActivityItem, FavoriteItem, PersonalFileItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class PersonalHubPage extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__section = new SynchedPropertySimpleOneWayPU(params.section, this, "section");
        this.__files = new SynchedPropertyObjectOneWayPU(params.files, this, "files");
        this.__activities = new SynchedPropertyObjectOneWayPU(params.activities, this, "activities");
        this.__favorites = new SynchedPropertyObjectOneWayPU(params.favorites, this, "favorites");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__query = new ObservedPropertySimplePU('', this, "query");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: PersonalHubPage_Params) {
        if (params.section === undefined) {
            this.__section.set('files');
        }
        if (params.files === undefined) {
            this.__files.set([]);
        }
        if (params.activities === undefined) {
            this.__activities.set([]);
        }
        if (params.favorites === undefined) {
            this.__favorites.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.query !== undefined) {
            this.query = params.query;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onRefresh !== undefined) {
            this.onRefresh = params.onRefresh;
        }
    }
    updateStateVars(params: PersonalHubPage_Params) {
        this.__section.reset(params.section);
        this.__files.reset(params.files);
        this.__activities.reset(params.activities);
        this.__favorites.reset(params.favorites);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__section.purgeDependencyOnElmtId(rmElmtId);
        this.__files.purgeDependencyOnElmtId(rmElmtId);
        this.__activities.purgeDependencyOnElmtId(rmElmtId);
        this.__favorites.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__query.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__section.aboutToBeDeleted();
        this.__files.aboutToBeDeleted();
        this.__activities.aboutToBeDeleted();
        this.__favorites.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__query.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __section: SynchedPropertySimpleOneWayPU<string>;
    get section() {
        return this.__section.get();
    }
    set section(newValue: string) {
        this.__section.set(newValue);
    }
    private __files: SynchedPropertySimpleOneWayPU<PersonalFileItem[]>;
    get files() {
        return this.__files.get();
    }
    set files(newValue: PersonalFileItem[]) {
        this.__files.set(newValue);
    }
    private __activities: SynchedPropertySimpleOneWayPU<ActivityItem[]>;
    get activities() {
        return this.__activities.get();
    }
    set activities(newValue: ActivityItem[]) {
        this.__activities.set(newValue);
    }
    private __favorites: SynchedPropertySimpleOneWayPU<FavoriteItem[]>;
    get favorites() {
        return this.__favorites.get();
    }
    set favorites(newValue: FavoriteItem[]) {
        this.__favorites.set(newValue);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(newValue: boolean) {
        this.__loading.set(newValue);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __query: ObservedPropertySimplePU<string>;
    get query() {
        return this.__query.get();
    }
    set query(newValue: string) {
        this.__query.set(newValue);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    title(): string { return this.section === 'files' ? '文件' : this.section === 'activities' ? '活动' : '收藏'; }
    FileRow(item: PersonalFileItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(20:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(21:7)", "entry");
            Stack.width(44);
            Stack.height(44);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(21:51)", "entry");
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(23:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.name);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(24:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.category ?? '其他'} · ${item.size_label ?? '未知大小'}`);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(25:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.updated_at ?? ''} · ${item.source ?? '当前账号'}`);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(26:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (item.is_favorite === true) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831606, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(29:9)", "entry");
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        SymbolGlyph.create({ "id": 125831605, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(31:9)", "entry");
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Row.pop();
    }
    ActivityRow(item: ActivityItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 7 });
            Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(37:5)", "entry");
            Column.width('100%');
            Column.padding(13);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(17);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(38:7)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.category ?? '校园活动');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(39:9)", "entry");
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
            Blank.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(40:9)", "entry");
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.status === 'closed' ? '已结束' : '报名中');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(40:18)", "entry");
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(42:7)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.summary ?? '暂无活动简介');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(43:7)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.width('100%');
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 10 });
            Row.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(44:7)", "entry");
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.author_name ?? '校园活动中心');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(45:9)", "entry");
            Text.fontColor(this.palette().primary);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.location ?? '地点待定');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(46:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
    }
    FavoriteRow(item: FavoriteItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(52:5)", "entry");
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(53:7)", "entry");
            Stack.width(44);
            Stack.height(44);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831606, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(53:51)", "entry");
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 4 });
            Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(55:7)", "entry");
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(56:9)", "entry");
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.subtitle ?? '已保存到当前账号');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(57:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.type ?? '内容'} · 收藏于 ${item.saved_at ?? ''}`);
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(58:9)", "entry");
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(64:5)", "entry");
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: `我的${this.title()}`, subtitle: '内容仅保存在当前登录账号下', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/profile/PersonalHubPage.ets", line: 65, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: `我的${this.title()}`,
                            subtitle: '内容仅保存在当前登录账号下',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: `我的${this.title()}`, subtitle: '内容仅保存在当前登录账号下', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 12 });
            Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(66:7)", "entry");
            Column.layoutWeight(1);
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 18 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 8 });
            Row.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(67:9)", "entry");
            Row.width('100%');
            Row.height(50);
            Row.padding({ left: 12, right: 12 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(68:11)", "entry");
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            TextInput.create({ placeholder: `搜索${this.title()}`, text: this.query });
            TextInput.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(69:11)", "entry");
            TextInput.layoutWeight(1);
            TextInput.height(43);
            TextInput.backgroundColor(Color.Transparent);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.onChange((value: string) => this.query = value);
        }, TextInput);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('刷新');
            Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(71:11)", "entry");
            Text.fontColor(this.palette().primary);
            Text.fontSize(11);
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        LoadingProgress.create();
                        LoadingProgress.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(75:11)", "entry");
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 40 });
                    }, LoadingProgress);
                });
            }
            else if (this.section === 'files') {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        If.create();
                        if (this.files.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Text.create('没有找到文件');
                                    Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(77:42)", "entry");
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Column.create();
                                    Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(78:18)", "entry");
                                    Column.padding({ left: 13, right: 13 });
                                    Column.backgroundColor(this.palette().surface);
                                    Column.borderRadius(18);
                                }, Column);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    ForEach.create();
                                    const forEachItemGenFunction = (_item, index: number) => {
                                        const item = _item;
                                        this.FileRow.bind(this)(item);
                                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                                            If.create();
                                            if (index < this.files.length - 1) {
                                                this.ifElseBranchUpdateFunction(0, () => {
                                                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                                                        Divider.create();
                                                        Divider.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(78:151)", "entry");
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
                                    this.forEachUpdateFunction(elmtId, this.files, forEachItemGenFunction, undefined, true, false);
                                }, ForEach);
                                ForEach.pop();
                                Column.pop();
                            });
                        }
                    }, If);
                    If.pop();
                });
            }
            else if (this.section === 'activities') {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        If.create();
                        if (this.activities.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Text.create('没有找到活动');
                                    Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(80:47)", "entry");
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Scroll.create();
                                    Scroll.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(81:18)", "entry");
                                    Scroll.layoutWeight(1);
                                    Scroll.scrollBar(BarState.Off);
                                }, Scroll);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Column.create({ space: 9 });
                                    Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(81:29)", "entry");
                                    Column.padding({ bottom: 20 });
                                }, Column);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    ForEach.create();
                                    const forEachItemGenFunction = _item => {
                                        const item = _item;
                                        this.ActivityRow.bind(this)(item);
                                    };
                                    this.forEachUpdateFunction(elmtId, this.activities, forEachItemGenFunction);
                                }, ForEach);
                                ForEach.pop();
                                Column.pop();
                                Scroll.pop();
                            });
                        }
                    }, If);
                    If.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(3, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        If.create();
                        if (this.favorites.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Text.create('还没有收藏');
                                    Text.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(83:46)", "entry");
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    Column.create();
                                    Column.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(84:18)", "entry");
                                    Column.padding({ left: 13, right: 13 });
                                    Column.backgroundColor(this.palette().surface);
                                    Column.borderRadius(18);
                                }, Column);
                                this.observeComponentCreation2((elmtId, isInitialRender) => {
                                    ForEach.create();
                                    const forEachItemGenFunction = (_item, index: number) => {
                                        const item = _item;
                                        this.FavoriteRow.bind(this)(item);
                                        this.observeComponentCreation2((elmtId, isInitialRender) => {
                                            If.create();
                                            if (index < this.favorites.length - 1) {
                                                this.ifElseBranchUpdateFunction(0, () => {
                                                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                                                        Divider.create();
                                                        Divider.debugLine("entry/src/main/ets/features/profile/PersonalHubPage.ets(84:159)", "entry");
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
                                    this.forEachUpdateFunction(elmtId, this.favorites, forEachItemGenFunction, undefined, true, false);
                                }, ForEach);
                                ForEach.pop();
                                Column.pop();
                            });
                        }
                    }, If);
                    If.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

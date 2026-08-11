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
    constructor(f11, g11, h11, i11 = -1, j11 = undefined, k11) {
        super(f11, h11, i11, k11);
        if (typeof j11 === "function") {
            this.paramsGenerator_ = j11;
        }
        this.__section = new SynchedPropertySimpleOneWayPU(g11.section, this, "section");
        this.__files = new SynchedPropertyObjectOneWayPU(g11.files, this, "files");
        this.__activities = new SynchedPropertyObjectOneWayPU(g11.activities, this, "activities");
        this.__favorites = new SynchedPropertyObjectOneWayPU(g11.favorites, this, "favorites");
        this.__loading = new SynchedPropertySimpleOneWayPU(g11.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(g11.darkMode, this, "darkMode");
        this.__query = new ObservedPropertySimplePU('', this, "query");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(g11);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(e11: PersonalHubPage_Params) {
        if (e11.section === undefined) {
            this.__section.set('files');
        }
        if (e11.files === undefined) {
            this.__files.set([]);
        }
        if (e11.activities === undefined) {
            this.__activities.set([]);
        }
        if (e11.favorites === undefined) {
            this.__favorites.set([]);
        }
        if (e11.loading === undefined) {
            this.__loading.set(false);
        }
        if (e11.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (e11.query !== undefined) {
            this.query = e11.query;
        }
        if (e11.onBack !== undefined) {
            this.onBack = e11.onBack;
        }
        if (e11.onRefresh !== undefined) {
            this.onRefresh = e11.onRefresh;
        }
    }
    updateStateVars(d11: PersonalHubPage_Params) {
        this.__section.reset(d11.section);
        this.__files.reset(d11.files);
        this.__activities.reset(d11.activities);
        this.__favorites.reset(d11.favorites);
        this.__loading.reset(d11.loading);
        this.__darkMode.reset(d11.darkMode);
    }
    purgeVariableDependenciesOnElmtId(c11) {
        this.__section.purgeDependencyOnElmtId(c11);
        this.__files.purgeDependencyOnElmtId(c11);
        this.__activities.purgeDependencyOnElmtId(c11);
        this.__favorites.purgeDependencyOnElmtId(c11);
        this.__loading.purgeDependencyOnElmtId(c11);
        this.__darkMode.purgeDependencyOnElmtId(c11);
        this.__query.purgeDependencyOnElmtId(c11);
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
    set section(b11: string) {
        this.__section.set(b11);
    }
    private __files: SynchedPropertySimpleOneWayPU<PersonalFileItem[]>;
    get files() {
        return this.__files.get();
    }
    set files(a11: PersonalFileItem[]) {
        this.__files.set(a11);
    }
    private __activities: SynchedPropertySimpleOneWayPU<ActivityItem[]>;
    get activities() {
        return this.__activities.get();
    }
    set activities(z10: ActivityItem[]) {
        this.__activities.set(z10);
    }
    private __favorites: SynchedPropertySimpleOneWayPU<FavoriteItem[]>;
    get favorites() {
        return this.__favorites.get();
    }
    set favorites(y10: FavoriteItem[]) {
        this.__favorites.set(y10);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(x10: boolean) {
        this.__loading.set(x10);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(w10: boolean) {
        this.__darkMode.set(w10);
    }
    private __query: ObservedPropertySimplePU<string>;
    get query() {
        return this.__query.get();
    }
    set query(v10: string) {
        this.__query.set(v10);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    title(): string { return this.section === 'files' ? '文件' : this.section === 'activities' ? '活动' : '收藏'; }
    FileRow(z9: PersonalFileItem, a10 = null) {
        this.observeComponentCreation2((t10, u10) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((r10, s10) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(44);
            Stack.height(44);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((p10, q10) => {
            SymbolGlyph.create({ "id": 125831910, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((n10, o10) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((l10, m10) => {
            Text.create(z9.name);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j10, k10) => {
            Text.create(`${z9.category ?? '其他'} · ${z9.size_label ?? '未知大小'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h10, i10) => {
            Text.create(`${z9.updated_at ?? ''} · ${z9.source ?? '当前账号'}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((b10, c10) => {
            If.create();
            if (z9.is_favorite === true) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((f10, g10) => {
                        SymbolGlyph.create({ "id": 125831606, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((d10, e10) => {
                        SymbolGlyph.create({ "id": 125831605, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
                        SymbolGlyph.fontSize(18);
                        SymbolGlyph.fontColor([this.palette().primary]);
                    }, SymbolGlyph);
                });
            }
        }, If);
        If.pop();
        Row.pop();
    }
    ActivityRow(d9: ActivityItem, e9 = null) {
        this.observeComponentCreation2((x9, y9) => {
            Column.create({ space: 7 });
            Column.width('100%');
            Column.padding(13);
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(17);
        }, Column);
        this.observeComponentCreation2((v9, w9) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((t9, u9) => {
            Text.create(d9.category ?? '校园活动');
            Text.fontColor(this.palette().primary);
            Text.fontSize(9);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r9, s9) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((p9, q9) => {
            Text.create(d9.status === 'closed' ? '已结束' : '报名中');
            Text.fontColor(this.palette().success);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((n9, o9) => {
            Text.create(d9.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(15);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((l9, m9) => {
            Text.create(d9.summary ?? '暂无活动简介');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.width('100%');
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((j9, k9) => {
            Row.create({ space: 10 });
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((h9, i9) => {
            Text.create(d9.author_name ?? '校园活动中心');
            Text.fontColor(this.palette().primary);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((f9, g9) => {
            Text.create(d9.location ?? '地点待定');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
        }, Text);
        Text.pop();
        Row.pop();
        Column.pop();
    }
    FavoriteRow(n8: FavoriteItem, o8 = null) {
        this.observeComponentCreation2((b9, c9) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 11, bottom: 11 });
        }, Row);
        this.observeComponentCreation2((z8, a9) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(44);
            Stack.height(44);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((x8, y8) => {
            SymbolGlyph.create({ "id": 125831606, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((v8, w8) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((t8, u8) => {
            Text.create(n8.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((r8, s8) => {
            Text.create(n8.subtitle ?? '已保存到当前账号');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((p8, q8) => {
            Text.create(`${n8.type ?? '内容'} · 收藏于 ${n8.saved_at ?? ''}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((l8, m8) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((h8, i8) => {
                if (i8) {
                    let j8 = new SecondaryHeader(this, { title: `我的${this.title()}`, subtitle: '内容仅保存在当前登录账号下', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, h8, () => { }, { page: "entry/src/main/ets/features/profile/PersonalHubPage.ets", line: 65, col: 7 });
                    ViewPU.create(j8);
                    let k8 = () => {
                        return {
                            title: `我的${this.title()}`,
                            subtitle: '内容仅保存在当前登录账号下',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    j8.paramsGenerator_ = k8;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(h8, {
                        title: `我的${this.title()}`, subtitle: '内容仅保存在当前登录账号下', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((f8, g8) => {
            Column.create({ space: 12 });
            Column.layoutWeight(1);
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 18 });
        }, Column);
        this.observeComponentCreation2((d8, e8) => {
            Row.create({ space: 8 });
            Row.width('100%');
            Row.height(50);
            Row.padding({ left: 12, right: 12 });
            Row.backgroundColor(this.palette().surface);
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(16);
        }, Row);
        this.observeComponentCreation2((b8, c8) => {
            SymbolGlyph.create({ "id": 125831500, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(17);
            SymbolGlyph.fontColor([this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((y7, z7) => {
            TextInput.create({ placeholder: `搜索${this.title()}`, text: this.query });
            TextInput.layoutWeight(1);
            TextInput.height(43);
            TextInput.backgroundColor(Color.Transparent);
            TextInput.fontColor(this.palette().text);
            TextInput.placeholderColor(this.palette().muted);
            TextInput.onChange((a8: string) => this.query = a8);
        }, TextInput);
        this.observeComponentCreation2((w7, x7) => {
            Text.create('刷新');
            Text.fontColor(this.palette().primary);
            Text.fontSize(11);
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((z5, a6) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((u7, v7) => {
                        LoadingProgress.create();
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin({ top: 40 });
                    }, LoadingProgress);
                });
            }
            else if (this.section === 'files') {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((e7, f7) => {
                        If.create();
                        if (this.files.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((s7, t7) => {
                                    Text.create('没有找到文件');
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((q7, r7) => {
                                    Column.create();
                                    Column.padding({ left: 13, right: 13 });
                                    Column.backgroundColor(this.palette().surface);
                                    Column.borderRadius(18);
                                }, Column);
                                this.observeComponentCreation2((g7, h7) => {
                                    ForEach.create();
                                    const i7 = (j7, k7: number) => {
                                        const l7 = j7;
                                        this.FileRow.bind(this)(l7);
                                        this.observeComponentCreation2((m7, n7) => {
                                            If.create();
                                            if (k7 < this.files.length - 1) {
                                                this.ifElseBranchUpdateFunction(0, () => {
                                                    this.observeComponentCreation2((o7, p7) => {
                                                        Divider.create();
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
                                    this.forEachUpdateFunction(g7, this.files, i7, undefined, true, false);
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
                    this.observeComponentCreation2((r6, s6) => {
                        If.create();
                        if (this.activities.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((c7, d7) => {
                                    Text.create('没有找到活动');
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((a7, b7) => {
                                    Scroll.create();
                                    Scroll.layoutWeight(1);
                                    Scroll.scrollBar(BarState.Off);
                                }, Scroll);
                                this.observeComponentCreation2((y6, z6) => {
                                    Column.create({ space: 9 });
                                    Column.padding({ bottom: 20 });
                                }, Column);
                                this.observeComponentCreation2((t6, u6) => {
                                    ForEach.create();
                                    const v6 = w6 => {
                                        const x6 = w6;
                                        this.ActivityRow.bind(this)(x6);
                                    };
                                    this.forEachUpdateFunction(t6, this.activities, v6);
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
                    this.observeComponentCreation2((b6, c6) => {
                        If.create();
                        if (this.favorites.length === 0) {
                            this.ifElseBranchUpdateFunction(0, () => {
                                this.observeComponentCreation2((p6, q6) => {
                                    Text.create('还没有收藏');
                                    Text.fontColor(this.palette().muted);
                                    Text.fontSize(12);
                                    Text.padding(34);
                                }, Text);
                                Text.pop();
                            });
                        }
                        else {
                            this.ifElseBranchUpdateFunction(1, () => {
                                this.observeComponentCreation2((n6, o6) => {
                                    Column.create();
                                    Column.padding({ left: 13, right: 13 });
                                    Column.backgroundColor(this.palette().surface);
                                    Column.borderRadius(18);
                                }, Column);
                                this.observeComponentCreation2((d6, e6) => {
                                    ForEach.create();
                                    const f6 = (g6, h6: number) => {
                                        const i6 = g6;
                                        this.FavoriteRow.bind(this)(i6);
                                        this.observeComponentCreation2((j6, k6) => {
                                            If.create();
                                            if (h6 < this.favorites.length - 1) {
                                                this.ifElseBranchUpdateFunction(0, () => {
                                                    this.observeComponentCreation2((l6, m6) => {
                                                        Divider.create();
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
                                    this.forEachUpdateFunction(d6, this.favorites, f6, undefined, true, false);
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

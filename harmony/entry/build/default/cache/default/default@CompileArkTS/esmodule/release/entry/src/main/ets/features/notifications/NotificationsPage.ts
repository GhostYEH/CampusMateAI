if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface NotificationsPage_Params {
    notices?: NoticeItem[];
    loading?: boolean;
    darkMode?: boolean;
    unreadOnly?: boolean;
    onBack?: () => void;
    onRefresh?: () => void;
}
import type { NoticeItem } from '../../data/Models';
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import { SecondaryHeader } from "@bundle:com.example.campusmate/entry/ets/ui/SecondaryHeader";
export class NotificationsPage extends ViewPU {
    constructor(q3, r3, s3, t3 = -1, u3 = undefined, v3) {
        super(q3, s3, t3, v3);
        if (typeof u3 === "function") {
            this.paramsGenerator_ = u3;
        }
        this.__notices = new SynchedPropertyObjectOneWayPU(r3.notices, this, "notices");
        this.__loading = new SynchedPropertySimpleOneWayPU(r3.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(r3.darkMode, this, "darkMode");
        this.__unreadOnly = new ObservedPropertySimplePU(false, this, "unreadOnly");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(r3);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(p3: NotificationsPage_Params) {
        if (p3.notices === undefined) {
            this.__notices.set([]);
        }
        if (p3.loading === undefined) {
            this.__loading.set(false);
        }
        if (p3.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (p3.unreadOnly !== undefined) {
            this.unreadOnly = p3.unreadOnly;
        }
        if (p3.onBack !== undefined) {
            this.onBack = p3.onBack;
        }
        if (p3.onRefresh !== undefined) {
            this.onRefresh = p3.onRefresh;
        }
    }
    updateStateVars(o3: NotificationsPage_Params) {
        this.__notices.reset(o3.notices);
        this.__loading.reset(o3.loading);
        this.__darkMode.reset(o3.darkMode);
    }
    purgeVariableDependenciesOnElmtId(n3) {
        this.__notices.purgeDependencyOnElmtId(n3);
        this.__loading.purgeDependencyOnElmtId(n3);
        this.__darkMode.purgeDependencyOnElmtId(n3);
        this.__unreadOnly.purgeDependencyOnElmtId(n3);
    }
    aboutToBeDeleted() {
        this.__notices.aboutToBeDeleted();
        this.__loading.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__unreadOnly.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __notices: SynchedPropertySimpleOneWayPU<NoticeItem[]>;
    get notices() {
        return this.__notices.get();
    }
    set notices(m3: NoticeItem[]) {
        this.__notices.set(m3);
    }
    private __loading: SynchedPropertySimpleOneWayPU<boolean>;
    get loading() {
        return this.__loading.get();
    }
    set loading(l3: boolean) {
        this.__loading.set(l3);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(k3: boolean) {
        this.__darkMode.set(k3);
    }
    private __unreadOnly: ObservedPropertySimplePU<boolean>;
    get unreadOnly() {
        return this.__unreadOnly.get();
    }
    set unreadOnly(j3: boolean) {
        this.__unreadOnly.set(j3);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    visible(): NoticeItem[] { return this.unreadOnly ? this.notices.filter((i3: NoticeItem) => i3.unread === true) : this.notices; }
    SourceRow(p2: Resource, q2: string, r2: string, s2: string, t2 = null) {
        this.observeComponentCreation2((g3, h3) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 10, bottom: 10 });
        }, Row);
        this.observeComponentCreation2((e3, f3) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((c3, d3) => {
            SymbolGlyph.create(p2);
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((a3, b3) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((y2, z2) => {
            Text.create(q2);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((w2, x2) => {
            Text.create(r2);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((u2, v2) => {
            Text.create(s2);
            Text.fontColor(this.palette().success);
            Text.fontSize(10);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        Row.pop();
    }
    NoticeRow(v1: NoticeItem, w1 = null) {
        this.observeComponentCreation2((n2, o2) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 12, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((l2, m2) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((j2, k2) => {
            SymbolGlyph.create({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((f2, g2) => {
            If.create();
            if (v1.unread === true) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((h2, i2) => {
                        Circle.create();
                        Circle.width(7);
                        Circle.height(7);
                        Circle.fill('#FFE35F42');
                        Circle.position({ x: 30, y: 4 });
                    }, Circle);
                });
            }
            else {
                this.ifElseBranchUpdateFunction(1, () => {
                });
            }
        }, If);
        If.pop();
        Stack.pop();
        this.observeComponentCreation2((d2, e2) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((b2, c2) => {
            Text.create(v1.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((z1, a2) => {
            Text.create(v1.content ?? '暂无详细内容');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((x1, y1) => {
            Text.create(`${v1.source ?? '校园通知'} · ${(v1.time ?? '').substring(0, Math.min(10, (v1.time ?? '').length))}`);
            Text.fontColor(this.palette().muted);
            Text.fontSize(9);
        }, Text);
        Text.pop();
        Column.pop();
        Row.pop();
    }
    initialRender() {
        this.observeComponentCreation2((t1, u1) => {
            Column.create();
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((p1, q1) => {
                if (q1) {
                    let r1 = new SecondaryHeader(this, { title: '通知整理', subtitle: '集中接收并整理校园通知', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, p1, () => { }, { page: "entry/src/main/ets/features/notifications/NotificationsPage.ets", line: 44, col: 7 });
                    ViewPU.create(r1);
                    let s1 = () => {
                        return {
                            title: '通知整理',
                            subtitle: '集中接收并整理校园通知',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    r1.paramsGenerator_ = s1;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(p1, {
                        title: '通知整理', subtitle: '集中接收并整理校园通知', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((n1, o1) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((l1, m1) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((j1, k1) => {
            Text.create('通知来源');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((h1, i1) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.SourceRow.bind(this)({ "id": 125832515, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '校园服务器', '公告、课程与截止事项', '已连接');
        this.observeComponentCreation2((f1, g1) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.SourceRow.bind(this)({ "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '学习通', '作为补充来源', '可设置');
        this.observeComponentCreation2((d1, e1) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.SourceRow.bind(this)({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '系统通知', '鸿蒙端使用站内通知替代第三方监听', '安全模式');
        Column.pop();
        this.observeComponentCreation2((b1, c1) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((z, a1) => {
            Text.create('最近收集');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((x, y) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((v, w) => {
            Text.create(this.unreadOnly ? '只看未读' : '全部');
            Text.fontColor(this.palette().primary);
            Text.fontSize(11);
            Text.onClick(() => this.unreadOnly = !this.unreadOnly);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((t, u) => {
            Text.create('刷新');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
            Text.margin({ left: 14 });
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((r, s) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((a, b) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((p, q) => {
                        LoadingProgress.create();
                        LoadingProgress.width(34);
                        LoadingProgress.height(34);
                        LoadingProgress.color(this.palette().primary);
                        LoadingProgress.margin(28);
                    }, LoadingProgress);
                });
            }
            else if (this.visible().length === 0) {
                this.ifElseBranchUpdateFunction(1, () => {
                    this.observeComponentCreation2((n, o) => {
                        Text.create('暂无校园通知');
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(12);
                        Text.padding(30);
                    }, Text);
                    Text.pop();
                });
            }
            else {
                this.ifElseBranchUpdateFunction(2, () => {
                    this.observeComponentCreation2((c, d) => {
                        ForEach.create();
                        const e = (g, h: number) => {
                            const i = g;
                            this.NoticeRow.bind(this)(i);
                            this.observeComponentCreation2((j, k) => {
                                If.create();
                                if (h < this.visible().length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((l, m) => {
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
                        this.forEachUpdateFunction(c, this.visible(), e, (f: NoticeItem) => f.id, true, false);
                    }, ForEach);
                    ForEach.pop();
                });
            }
        }, If);
        If.pop();
        Column.pop();
        Column.pop();
        Scroll.pop();
        Column.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

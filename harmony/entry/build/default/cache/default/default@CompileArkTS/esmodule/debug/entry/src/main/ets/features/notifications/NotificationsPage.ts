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
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__notices = new SynchedPropertyObjectOneWayPU(params.notices, this, "notices");
        this.__loading = new SynchedPropertySimpleOneWayPU(params.loading, this, "loading");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__unreadOnly = new ObservedPropertySimplePU(false, this, "unreadOnly");
        this.onBack = () => { };
        this.onRefresh = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: NotificationsPage_Params) {
        if (params.notices === undefined) {
            this.__notices.set([]);
        }
        if (params.loading === undefined) {
            this.__loading.set(false);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.unreadOnly !== undefined) {
            this.unreadOnly = params.unreadOnly;
        }
        if (params.onBack !== undefined) {
            this.onBack = params.onBack;
        }
        if (params.onRefresh !== undefined) {
            this.onRefresh = params.onRefresh;
        }
    }
    updateStateVars(params: NotificationsPage_Params) {
        this.__notices.reset(params.notices);
        this.__loading.reset(params.loading);
        this.__darkMode.reset(params.darkMode);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__notices.purgeDependencyOnElmtId(rmElmtId);
        this.__loading.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__unreadOnly.purgeDependencyOnElmtId(rmElmtId);
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
    set notices(newValue: NoticeItem[]) {
        this.__notices.set(newValue);
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
    private __unreadOnly: ObservedPropertySimplePU<boolean>;
    get unreadOnly() {
        return this.__unreadOnly.get();
    }
    set unreadOnly(newValue: boolean) {
        this.__unreadOnly.set(newValue);
    }
    private onBack: () => void;
    private onRefresh: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    visible(): NoticeItem[] { return this.unreadOnly ? this.notices.filter((item: NoticeItem) => item.unread === true) : this.notices; }
    SourceRow(symbol: Resource, title: string, subtitle: string, status: string, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 10, bottom: 10 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(symbol);
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(title);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(subtitle);
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(status);
            Text.fontColor(this.palette().success);
            Text.fontSize(10);
            Text.fontWeight(FontWeight.Medium);
        }, Text);
        Text.pop();
        Row.pop();
    }
    NoticeRow(item: NoticeItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create({ space: 11 });
            Row.width('100%');
            Row.padding({ top: 12, bottom: 12 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(42);
            Stack.backgroundColor(this.palette().soft);
            Stack.borderRadius(13);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create({ "id": 125831513, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(20);
            SymbolGlyph.fontColor([this.palette().primary]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (item.unread === true) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 4 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(13);
            Text.fontWeight(FontWeight.Bold);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.content ?? '暂无详细内容');
            Text.fontColor(this.palette().muted);
            Text.fontSize(10);
            Text.maxLines(2);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(`${item.source ?? '校园通知'} · ${(item.time ?? '').substring(0, Math.min(10, (item.time ?? '').length))}`);
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
            Column.width('100%');
            Column.height('100%');
            Column.backgroundColor(this.palette().background);
        }, Column);
        {
            this.observeComponentCreation2((elmtId, isInitialRender) => {
                if (isInitialRender) {
                    let componentCall = new SecondaryHeader(this, { title: '通知整理', subtitle: '集中接收并整理校园通知', darkMode: this.darkMode, onBack: () => this.onBack() }, undefined, elmtId, () => { }, { page: "entry/src/main/ets/features/notifications/NotificationsPage.ets", line: 44, col: 7 });
                    ViewPU.create(componentCall);
                    let paramsLambda = () => {
                        return {
                            title: '通知整理',
                            subtitle: '集中接收并整理校园通知',
                            darkMode: this.darkMode,
                            onBack: () => this.onBack()
                        };
                    };
                    componentCall.paramsGenerator_ = paramsLambda;
                }
                else {
                    this.updateStateVarsOfChildByElmtId(elmtId, {
                        title: '通知整理', subtitle: '集中接收并整理校园通知', darkMode: this.darkMode
                    });
                }
            }, { name: "SecondaryHeader" });
        }
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Scroll.create();
            Scroll.layoutWeight(1);
            Scroll.width('100%');
            Scroll.scrollBar(BarState.Off);
        }, Scroll);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 13 });
            Column.width('100%');
            Column.padding({ left: 14, right: 14, bottom: 24 });
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('通知来源');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
            Text.width('100%');
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.SourceRow.bind(this)({ "id": 125832515, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '校园服务器', '公告、课程与截止事项', '已连接');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.SourceRow.bind(this)({ "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '学习通', '作为补充来源', '可设置');
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Divider.create();
            Divider.color(this.palette().line);
        }, Divider);
        this.SourceRow.bind(this)({ "id": 125832274, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, '系统通知', '鸿蒙端使用站内通知替代第三方监听', '安全模式');
        Column.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.width('100%');
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('最近收集');
            Text.fontColor(this.palette().text);
            Text.fontSize(17);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Blank.create();
        }, Blank);
        Blank.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(this.unreadOnly ? '只看未读' : '全部');
            Text.fontColor(this.palette().primary);
            Text.fontSize(11);
            Text.onClick(() => this.unreadOnly = !this.unreadOnly);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create('刷新');
            Text.fontColor(this.palette().muted);
            Text.fontSize(11);
            Text.margin({ left: 14 });
            Text.onClick(() => this.onRefresh());
        }, Text);
        Text.pop();
        Row.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create();
            Column.width('100%');
            Column.padding({ left: 13, right: 13 });
            Column.backgroundColor(this.palette().surface);
            Column.borderRadius(18);
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (this.loading) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        ForEach.create();
                        const forEachItemGenFunction = (_item, index: number) => {
                            const item = _item;
                            this.NoticeRow.bind(this)(item);
                            this.observeComponentCreation2((elmtId, isInitialRender) => {
                                If.create();
                                if (index < this.visible().length - 1) {
                                    this.ifElseBranchUpdateFunction(0, () => {
                                        this.observeComponentCreation2((elmtId, isInitialRender) => {
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
                        this.forEachUpdateFunction(elmtId, this.visible(), forEachItemGenFunction, (item: NoticeItem) => item.id, true, false);
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

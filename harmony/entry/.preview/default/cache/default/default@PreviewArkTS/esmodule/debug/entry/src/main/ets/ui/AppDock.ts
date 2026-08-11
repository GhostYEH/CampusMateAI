if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface AppDock_Params {
    activeTab?: number;
    darkMode?: boolean;
    pendingCount?: number;
    onNavigate?: (index: number) => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
interface DockItem {
    label: string;
    symbol: Resource;
    index: number;
}
export class AppDock extends ViewPU {
    constructor(parent, params, __localStorage, elmtId = -1, paramsLambda = undefined, extraInfo) {
        super(parent, __localStorage, elmtId, extraInfo);
        if (typeof paramsLambda === "function") {
            this.paramsGenerator_ = paramsLambda;
        }
        this.__activeTab = new SynchedPropertySimpleOneWayPU(params.activeTab, this, "activeTab");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(params.darkMode, this, "darkMode");
        this.__pendingCount = new SynchedPropertySimpleOneWayPU(params.pendingCount, this, "pendingCount");
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(params);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(params: AppDock_Params) {
        if (params.activeTab === undefined) {
            this.__activeTab.set(0);
        }
        if (params.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (params.pendingCount === undefined) {
            this.__pendingCount.set(0);
        }
        if (params.onNavigate !== undefined) {
            this.onNavigate = params.onNavigate;
        }
    }
    updateStateVars(params: AppDock_Params) {
        this.__activeTab.reset(params.activeTab);
        this.__darkMode.reset(params.darkMode);
        this.__pendingCount.reset(params.pendingCount);
    }
    purgeVariableDependenciesOnElmtId(rmElmtId) {
        this.__activeTab.purgeDependencyOnElmtId(rmElmtId);
        this.__darkMode.purgeDependencyOnElmtId(rmElmtId);
        this.__pendingCount.purgeDependencyOnElmtId(rmElmtId);
    }
    aboutToBeDeleted() {
        this.__activeTab.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        this.__pendingCount.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __activeTab: SynchedPropertySimpleOneWayPU<number>;
    get activeTab() {
        return this.__activeTab.get();
    }
    set activeTab(newValue: number) {
        this.__activeTab.set(newValue);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(newValue: boolean) {
        this.__darkMode.set(newValue);
    }
    private __pendingCount: SynchedPropertySimpleOneWayPU<number>;
    get pendingCount() {
        return this.__pendingCount.get();
    }
    set pendingCount(newValue: number) {
        this.__pendingCount.set(newValue);
    }
    private onNavigate: (index: number) => void;
    palette(): CampusPalette {
        return this.darkMode ? darkPalette : lightPalette;
    }
    DockItemView(item: DockItem, parent = null) {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Column.create({ space: 2 });
            Column.debugLine("entry/src/main/ets/ui/AppDock.ets(22:5)", "entry");
            Column.layoutWeight(1);
            Column.height(54);
            Column.justifyContent(FlexAlign.Center);
            Column.alignItems(HorizontalAlign.Center);
            Column.backgroundColor(this.activeTab === item.index ? this.palette().soft : Color.Transparent);
            Column.border({
                width: this.activeTab === item.index ? 1 : 0,
                color: this.activeTab === item.index ? this.palette().primary : Color.Transparent
            });
            Column.borderRadius(27);
            Column.margin({ left: 2, right: 2 });
            Column.onClick(() => this.onNavigate(item.index));
        }, Column);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.debugLine("entry/src/main/ets/ui/AppDock.ets(23:7)", "entry");
            Stack.width(42);
            Stack.height(27);
        }, Stack);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            SymbolGlyph.create(item.symbol);
            SymbolGlyph.debugLine("entry/src/main/ets/ui/AppDock.ets(24:9)", "entry");
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium);
            SymbolGlyph.fontColor([this.activeTab === item.index ? this.palette().primary : this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            If.create();
            if (item.index === 2 && this.pendingCount > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((elmtId, isInitialRender) => {
                        Text.create(this.pendingCount > 9 ? '9+' : this.pendingCount.toString());
                        Text.debugLine("entry/src/main/ets/ui/AppDock.ets(29:11)", "entry");
                        Text.fontColor('#FFFFFFFF');
                        Text.fontSize(8);
                        Text.fontWeight(FontWeight.Bold);
                        Text.textAlign(TextAlign.Center);
                        Text.width(16);
                        Text.height(16);
                        Text.backgroundColor('#FFED6E52');
                        Text.borderRadius(8);
                        Text.position({ x: 28, y: 0 });
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
        Stack.pop();
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Text.create(item.label);
            Text.debugLine("entry/src/main/ets/ui/AppDock.ets(43:7)", "entry");
            Text.fontColor(this.activeTab === item.index ? this.palette().primary : this.palette().muted);
            Text.fontSize(item.index === 3 ? 8.5 : 10);
            Text.fontWeight(this.activeTab === item.index ? FontWeight.Bold : FontWeight.Medium);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
    }
    initialRender() {
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            Row.create();
            Row.debugLine("entry/src/main/ets/ui/AppDock.ets(64:5)", "entry");
            Row.width('100%');
            Row.height(76);
            Row.padding({ left: 7, right: 7, top: 7, bottom: 7 });
            Row.alignItems(VerticalAlign.Center);
            Row.backgroundColor(this.darkMode ? '#EB14272E' : '#EBFFFFFFFF');
            Row.border({ width: 1, color: this.palette().line });
            Row.borderRadius(38);
            Row.shadow({ radius: 18, color: this.darkMode ? '#66000000' : '#240B1830', offsetY: 6 });
            Row.margin({ left: 14, right: 14, bottom: 10 });
        }, Row);
        this.observeComponentCreation2((elmtId, isInitialRender) => {
            ForEach.create();
            const forEachItemGenFunction = _item => {
                const item = _item;
                this.DockItemView.bind(this)(item);
            };
            this.forEachUpdateFunction(elmtId, [
                { label: '首页', symbol: { "id": 125831533, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 0 },
                { label: '课程', symbol: { "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 1 },
                { label: '待办', symbol: { "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 2 },
                { label: 'AI 校园助手', symbol: { "id": 125833267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 3 },
                { label: '我的', symbol: { "id": 125832135, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 4 }
            ], forEachItemGenFunction);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

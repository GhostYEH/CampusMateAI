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
    constructor(p17, q17, r17, s17 = -1, t17 = undefined, u17) {
        super(p17, r17, s17, u17);
        if (typeof t17 === "function") {
            this.paramsGenerator_ = t17;
        }
        this.__activeTab = new SynchedPropertySimpleOneWayPU(q17.activeTab, this, "activeTab");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(q17.darkMode, this, "darkMode");
        this.__pendingCount = new SynchedPropertySimpleOneWayPU(q17.pendingCount, this, "pendingCount");
        this.onNavigate = () => { };
        this.setInitiallyProvidedValue(q17);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(o17: AppDock_Params) {
        if (o17.activeTab === undefined) {
            this.__activeTab.set(0);
        }
        if (o17.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (o17.pendingCount === undefined) {
            this.__pendingCount.set(0);
        }
        if (o17.onNavigate !== undefined) {
            this.onNavigate = o17.onNavigate;
        }
    }
    updateStateVars(n17: AppDock_Params) {
        this.__activeTab.reset(n17.activeTab);
        this.__darkMode.reset(n17.darkMode);
        this.__pendingCount.reset(n17.pendingCount);
    }
    purgeVariableDependenciesOnElmtId(m17) {
        this.__activeTab.purgeDependencyOnElmtId(m17);
        this.__darkMode.purgeDependencyOnElmtId(m17);
        this.__pendingCount.purgeDependencyOnElmtId(m17);
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
    set activeTab(l17: number) {
        this.__activeTab.set(l17);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(k17: boolean) {
        this.__darkMode.set(k17);
    }
    private __pendingCount: SynchedPropertySimpleOneWayPU<number>;
    get pendingCount() {
        return this.__pendingCount.get();
    }
    set pendingCount(j17: number) {
        this.__pendingCount.set(j17);
    }
    private onNavigate: (index: number) => void;
    palette(): CampusPalette {
        return this.darkMode ? darkPalette : lightPalette;
    }
    DockItemView(v16: DockItem, w16 = null) {
        this.observeComponentCreation2((h17, i17) => {
            Column.create({ space: 2 });
            Column.layoutWeight(1);
            Column.height(54);
            Column.justifyContent(FlexAlign.Center);
            Column.alignItems(HorizontalAlign.Center);
            Column.backgroundColor(this.activeTab === v16.index ? this.palette().soft : Color.Transparent);
            Column.border({
                width: this.activeTab === v16.index ? 1 : 0,
                color: this.activeTab === v16.index ? this.palette().primary : Color.Transparent
            });
            Column.borderRadius(27);
            Column.margin({ left: 2, right: 2 });
            Column.onClick(() => this.onNavigate(v16.index));
        }, Column);
        this.observeComponentCreation2((f17, g17) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(42);
            Stack.height(27);
        }, Stack);
        this.observeComponentCreation2((d17, e17) => {
            SymbolGlyph.create(v16.symbol);
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontWeight(this.activeTab === v16.index ? FontWeight.Bold : FontWeight.Medium);
            SymbolGlyph.fontColor([this.activeTab === v16.index ? this.palette().primary : this.palette().muted]);
        }, SymbolGlyph);
        this.observeComponentCreation2((z16, a17) => {
            If.create();
            if (v16.index === 2 && this.pendingCount > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((b17, c17) => {
                        Text.create(this.pendingCount > 9 ? '9+' : this.pendingCount.toString());
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
        this.observeComponentCreation2((x16, y16) => {
            Text.create(v16.label);
            Text.fontColor(this.activeTab === v16.index ? this.palette().primary : this.palette().muted);
            Text.fontSize(v16.index === 3 ? 8.5 : 10);
            Text.fontWeight(this.activeTab === v16.index ? FontWeight.Bold : FontWeight.Medium);
            Text.maxLines(1);
        }, Text);
        Text.pop();
        Column.pop();
    }
    initialRender() {
        this.observeComponentCreation2((t16, u16) => {
            Row.create();
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
        this.observeComponentCreation2((o16, p16) => {
            ForEach.create();
            const q16 = r16 => {
                const s16 = r16;
                this.DockItemView.bind(this)(s16);
            };
            this.forEachUpdateFunction(o16, [
                { label: '首页', symbol: { "id": 125831533, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 0 },
                { label: '课程', symbol: { "id": 125831935, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 1 },
                { label: '待办', symbol: { "id": 125831133, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 2 },
                { label: 'AI 校园助手', symbol: { "id": 125833267, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 3 },
                { label: '我的', symbol: { "id": 125832135, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" }, index: 4 }
            ], q16);
        }, ForEach);
        ForEach.pop();
        Row.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

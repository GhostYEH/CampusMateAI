if (!("finalizeConstruction" in ViewPU.prototype)) {
    Reflect.set(ViewPU.prototype, "finalizeConstruction", () => { });
}
interface SecondaryHeader_Params {
    title?: string;
    subtitle?: string;
    darkMode?: boolean;
    onBack?: () => void;
}
import { darkPalette, lightPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
import type { CampusPalette } from "@bundle:com.example.campusmate/entry/ets/ui/Theme";
export class SecondaryHeader extends ViewPU {
    constructor(i35, j35, k35, l35 = -1, m35 = undefined, n35) {
        super(i35, k35, l35, n35);
        if (typeof m35 === "function") {
            this.paramsGenerator_ = m35;
        }
        this.__title = new SynchedPropertySimpleOneWayPU(j35.title, this, "title");
        this.__subtitle = new SynchedPropertySimpleOneWayPU(j35.subtitle, this, "subtitle");
        this.__darkMode = new SynchedPropertySimpleOneWayPU(j35.darkMode, this, "darkMode");
        this.onBack = () => { };
        this.setInitiallyProvidedValue(j35);
        this.finalizeConstruction();
    }
    setInitiallyProvidedValue(h35: SecondaryHeader_Params) {
        if (h35.title === undefined) {
            this.__title.set('');
        }
        if (h35.subtitle === undefined) {
            this.__subtitle.set('');
        }
        if (h35.darkMode === undefined) {
            this.__darkMode.set(false);
        }
        if (h35.onBack !== undefined) {
            this.onBack = h35.onBack;
        }
    }
    updateStateVars(g35: SecondaryHeader_Params) {
        this.__title.reset(g35.title);
        this.__subtitle.reset(g35.subtitle);
        this.__darkMode.reset(g35.darkMode);
    }
    purgeVariableDependenciesOnElmtId(f35) {
        this.__title.purgeDependencyOnElmtId(f35);
        this.__subtitle.purgeDependencyOnElmtId(f35);
        this.__darkMode.purgeDependencyOnElmtId(f35);
    }
    aboutToBeDeleted() {
        this.__title.aboutToBeDeleted();
        this.__subtitle.aboutToBeDeleted();
        this.__darkMode.aboutToBeDeleted();
        SubscriberManager.Get().delete(this.id__());
        this.aboutToBeDeletedInternal();
    }
    private __title: SynchedPropertySimpleOneWayPU<string>;
    get title() {
        return this.__title.get();
    }
    set title(e35: string) {
        this.__title.set(e35);
    }
    private __subtitle: SynchedPropertySimpleOneWayPU<string>;
    get subtitle() {
        return this.__subtitle.get();
    }
    set subtitle(d35: string) {
        this.__subtitle.set(d35);
    }
    private __darkMode: SynchedPropertySimpleOneWayPU<boolean>;
    get darkMode() {
        return this.__darkMode.get();
    }
    set darkMode(c35: boolean) {
        this.__darkMode.set(c35);
    }
    private onBack: () => void;
    palette(): CampusPalette { return this.darkMode ? darkPalette : lightPalette; }
    initialRender() {
        this.observeComponentCreation2((a35, b35) => {
            Row.create({ space: 12 });
            Row.width('100%');
            Row.padding({ left: 14, right: 14, top: 12, bottom: 10 });
            Row.alignItems(VerticalAlign.Center);
        }, Row);
        this.observeComponentCreation2((y34, z34) => {
            Stack.create({ alignContent: Alignment.Center });
            Stack.width(40);
            Stack.height(40);
            Stack.backgroundColor(this.palette().surface);
            Stack.borderRadius(20);
            Stack.border({ width: 1, color: this.palette().line });
            Stack.onClick(() => this.onBack());
        }, Stack);
        this.observeComponentCreation2((w34, x34) => {
            SymbolGlyph.create({ "id": 125832679, "type": 40000, params: [], "bundleName": "com.example.campusmate", "moduleName": "entry" });
            SymbolGlyph.fontSize(21);
            SymbolGlyph.fontColor([this.palette().text]);
        }, SymbolGlyph);
        Stack.pop();
        this.observeComponentCreation2((u34, v34) => {
            Column.create({ space: 3 });
            Column.layoutWeight(1);
            Column.alignItems(HorizontalAlign.Start);
        }, Column);
        this.observeComponentCreation2((s34, t34) => {
            Text.create(this.title);
            Text.fontColor(this.palette().text);
            Text.fontSize(25);
            Text.fontWeight(FontWeight.Bold);
        }, Text);
        Text.pop();
        this.observeComponentCreation2((o34, p34) => {
            If.create();
            if (this.subtitle.length > 0) {
                this.ifElseBranchUpdateFunction(0, () => {
                    this.observeComponentCreation2((q34, r34) => {
                        Text.create(this.subtitle);
                        Text.fontColor(this.palette().muted);
                        Text.fontSize(11);
                        Text.maxLines(1);
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
        Column.pop();
        Row.pop();
    }
    rerender() {
        this.updateDirtyElements();
    }
}

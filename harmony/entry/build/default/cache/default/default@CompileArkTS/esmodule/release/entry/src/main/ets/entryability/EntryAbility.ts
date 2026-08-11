import type AbilityConstant from "@ohos:app.ability.AbilityConstant";
import UIAbility from "@ohos:app.ability.UIAbility";
import type Want from "@ohos:app.ability.Want";
import type window from "@ohos:window";
export default class EntryAbility extends UIAbility {
    onCreate(e: Want, f: AbilityConstant.LaunchParam): void { }
    onWindowStageCreate(c: window.WindowStage): void {
        c.loadContent('pages/Index', (d) => {
            if (d.code) {
                return;
            }
        });
    }
}

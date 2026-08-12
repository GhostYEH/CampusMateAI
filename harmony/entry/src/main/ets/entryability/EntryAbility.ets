import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {}

  onWindowStageCreate(windowStage: window.WindowStage): void {
    const mainWindow = windowStage.getMainWindowSync();
    mainWindow.setWindowLayoutFullScreen(true).catch(() => {});
    mainWindow.setWindowSystemBarEnable(['status', 'navigation']).catch(() => {});
    mainWindow.setWindowSystemBarProperties({
      statusBarColor: '#00000000',
      isStatusBarLightIcon: false,
      navigationBarColor: '#00000000',
      isNavigationBarLightIcon: false
    }).catch(() => {});
    windowStage.loadContent('pages/Index', (err) => { if (err.code) { return; } });
  }

  onWindowStageDestroy(): void {}
}

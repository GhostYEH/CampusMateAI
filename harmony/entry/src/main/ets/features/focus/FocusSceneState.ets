export type FocusDisplayMode = 'IMMERSIVE' | 'STANDARD';
export type FocusSceneId = 'RAINY_ROOM' | 'QUIET_LIBRARY' | 'FOREST_MORNING';

export interface FocusSceneOption {
  id: FocusSceneId;
  title: string;
  subtitle: string;
  asset: string;
}

const SCENES: FocusSceneOption[] = [
  { id: 'RAINY_ROOM', title: '雨夜书桌', subtitle: '让雨声般的节奏陪你沉下来', asset: 'focus_scene_rainy_room.webp' },
  { id: 'QUIET_LIBRARY', title: '静谧图书馆', subtitle: '适合阅读与长时间深度学习', asset: 'focus_scene_quiet_library.webp' },
  { id: 'FOREST_MORNING', title: '清晨森林', subtitle: '清亮一点，重新找回学习能量', asset: 'focus_scene_forest_morning.webp' }
];

export class FocusSceneState {
  static defaultDisplayMode(): FocusDisplayMode { return 'IMMERSIVE'; }

  static toggleDisplayMode(mode: FocusDisplayMode): FocusDisplayMode {
    return mode === 'IMMERSIVE' ? 'STANDARD' : 'IMMERSIVE';
  }

  static normalizeScene(value: string): FocusSceneId {
    if (value === 'QUIET_LIBRARY' || value === 'FOREST_MORNING') return value;
    return 'RAINY_ROOM';
  }

  static assetName(scene: FocusSceneId): string {
    return FocusSceneState.scene(scene).asset;
  }

  static scene(scene: FocusSceneId): FocusSceneOption {
    return SCENES.find((item: FocusSceneOption): boolean => item.id === scene) ?? SCENES[0];
  }

  static scenes(): FocusSceneOption[] { return SCENES; }
}

export interface LiquidGlassDockStyle {
  backdropBlur: number;
  surfaceColor: string;
  highlightColor: string;
  selectedSurfaceColor: string;
  selectedBorderColor: string;
  shadowColor: string;
  motionDuration: number;
  clickGlowEnabled: boolean;
  clickGlowDuration: number;
  clickGlowDiameter: number;
  clickGlowColor: string;
}

export function liquidGlassDockStyle(darkMode: boolean, reduceMotion: boolean): LiquidGlassDockStyle {
  return {
    backdropBlur: 32,
    surfaceColor: darkMode ? '#73162236' : '#66FFFFFF',
    highlightColor: darkMode ? '#55FFFFFF' : '#99FFFFFF',
    selectedSurfaceColor: darkMode ? '#526F78FF' : '#426C63FF',
    selectedBorderColor: darkMode ? '#709CC7D0' : '#705B68F2',
    shadowColor: darkMode ? '#80000000' : '#260B1830',
    motionDuration: reduceMotion ? 0 : 260,
    clickGlowEnabled: !reduceMotion,
    clickGlowDuration: reduceMotion ? 0 : 300,
    clickGlowDiameter: 52,
    clickGlowColor: darkMode ? '#B86F78FF' : '#B85B68F2'
  };
}

export interface LiquidGlassDockStyle {
  backdropBlur: number;
  surfaceColor: string;
  highlightColor: string;
  selectedSurfaceColor: string;
  selectedBorderColor: string;
  shadowColor: string;
  motionDuration: number;
  pressScale: number;
  showBottomIndicator: boolean;
  pressWaveEnabled: boolean;
  pressWaveDuration: number;
  pressWaveDiameter: number;
  pressWaveColor: string;
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
    pressScale: reduceMotion ? 1.0 : 0.92,
    showBottomIndicator: false,
    pressWaveEnabled: !reduceMotion,
    pressWaveDuration: reduceMotion ? 0 : 420,
    pressWaveDiameter: 76,
    pressWaveColor: darkMode ? '#669CC7D0' : '#665B68F2'
  };
}

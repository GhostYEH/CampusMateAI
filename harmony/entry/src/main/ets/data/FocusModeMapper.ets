import { FocusMode } from './Models';

export class FocusModeMapper {
  static fromLabel(label: string): FocusMode {
    if (label === '短休息') return 'short_break';
    if (label === '长休息') return 'long_break';
    return 'focus';
  }

  static toLabel(mode: FocusMode): string {
    if (mode === 'short_break') return '短休息';
    if (mode === 'long_break') return '长休息';
    return '专注';
  }
}
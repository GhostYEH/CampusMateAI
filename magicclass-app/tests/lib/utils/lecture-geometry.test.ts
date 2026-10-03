import { describe, expect, it } from 'vitest';
import type { PPTLineElement, PPTTextElement } from '@magicclass/dsl';
import { getElementPercentageGeometry as appGeometry } from '@/lib/utils/geometry';
import { getElementPercentageGeometry as rendererGeometry } from '@/packages/@magicclass/renderer/src/utils/geometry';
import { getElementPercentageGeometry as videoGeometry } from '@/lib/video-export/geometry';

const line: PPTLineElement = {
  type: 'line', id: 'arrow', left: 100, top: 50, width: 2,
  start: [0, 0], end: [200, 100], style: 'solid', color: '#000', points: ['', 'arrow'],
};

describe('lecture pointer geometry', () => {
  for (const [name, geometry] of [['app', appGeometry], ['renderer', rendererGeometry], ['video', videoGeometry]] as const) {
    it(`${name} resolves a legal arrow without height using its endpoints`, () => {
      const result = geometry(line)!;
      expect(result.centerX).toBe(20);
      expect(result.centerY).toBeCloseTo(100 / 562.5 * 100);
      expect(result.w).toBe(20); // stroke width is not the line's extent
      expect(result.h).toBeCloseTo(100 / 562.5 * 100);
      expect(geometry({ ...line, end: [-100, -50] })?.x).toBe(0);
    });
    it(`${name} includes bent/curve control points in its bounds`, () => {
      expect(geometry({ ...line, broken: [-100, 150], cubic: [[250, 50], [50, 75]] })?.w).toBe(30);
      expect(geometry({ ...line, cubic: [[250, 50], [50, 75]] })?.w).toBe(25);
      expect(geometry({ ...line, broken2: [400, 10000] })?.h).toBeCloseTo(100 / 562.5 * 100);
    });
  }
  it('app and renderer use the actual imported slide dimensions', () => {
    const text = { type: 'text', id: 'title', left: 800, top: 550, width: 200, height: 100 } as PPTTextElement;
    for (const geometry of [appGeometry, rendererGeometry]) {
      expect(geometry(text, 2000, 0.75)).toMatchObject({ centerX: 45, centerY: 40 });
      expect(geometry(line, 2000, 0.75)).toMatchObject({ centerX: 10 });
    }
  });
});

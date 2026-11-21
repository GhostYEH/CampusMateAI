import { describe, expect, it, vi } from 'vitest';
import { generateSceneActions, generateSceneContent } from '@magicclass/generation';
import type { SceneOutline } from '@/lib/types/generation';

const outline: SceneOutline = {
  id: 'ohm', order: 0, type: 'interactive', title: '欧姆定律',
  description: '观察两项参数与结果的关系', keyPoints: ['电压除以电阻'],
  widgetType: 'simulation', widgetOutline: { concept: '电流', keyVariables: ['电压', '电阻'] },
};

const modelOutput = {
  description: '观察电流随电压变化。',
  controls: [
    { id: 'voltage', label: '电压', unit: 'V', min: 0, max: 12, step: 1, value: 6 },
    { id: 'resistance', label: '电阻', unit: 'Ω', min: 1, max: 10, step: 1, value: 3 },
  ],
  resultLabel: '电流', resultUnit: 'A', expression: ['voltage', 'resistance', '/'],
  chartParameter: 'voltage', presets: [{ label: '9 V', values: { voltage: 9 } }],
};

describe('parameter experiment generation', () => {
  it('delivers shared arithmetic data and executable browser controls', async () => {
    const config = { ...modelOutput, description: '</script><script>example()</script>@MOUNT@' };
    const model = vi.fn(async () => JSON.stringify(config));
    const content = await generateSceneContent(outline, model);
    expect(model).toHaveBeenCalledTimes(1);
    if (!content || !('html' in content)) throw new Error('Missing interactive experiment');
    expect(content.widgetConfig).toMatchObject({ nativeRenderer: 'classroom-parameter-experiment/1', ...config });
    const embedded = /id="widget-config">([\s\S]*?)<\/script>/.exec(content.html)?.[1];
    expect(embedded).toBeTruthy();
    expect(JSON.parse(embedded!)).toEqual(content.widgetConfig);
    expect(content.html).not.toContain('</script><script>example()');
    const script = /<script>([\s\S]*?)<\/script>/.exec(content.html)?.[1];
    expect(script).toBeTruthy();
    expect(() => new Function(script!)).not.toThrow();
  });

  it('retains course-specific web controls when numeric data is invalid', async () => {
    const model = vi.fn<() => Promise<string>>()
      .mockResolvedValueOnce(JSON.stringify({ ...modelOutput, expression: ['mystery', 'voltage', '+'] }))
      .mockResolvedValueOnce('<!doctype html><html><body><div id="wiring">Connect</div></body></html>');
    const content = await generateSceneContent(outline, model);
    expect(model).toHaveBeenCalledTimes(2);
    expect(content).toMatchObject({ html: expect.stringContaining('wiring') });
  });

  it('keeps only valid changes and highlights so new data stays usable on Android', async () => {
    const content = await generateSceneContent(outline, async () => JSON.stringify(modelOutput));
    if (!content || !('html' in content)) throw new Error('Missing interactive experiment');
    const actions = await generateSceneActions(outline, content, async () => JSON.stringify([
      { type: 'text', content: '先将电压调高。' },
      { type: 'action', name: 'widget_highlight', params: { target: '#parameter-voltage' } },
      { type: 'action', name: 'widget_setState', params: { state: { voltage: 9 } } },
      { type: 'action', name: 'widget_setState', params: { state: { voltage: 900 } } },
      { type: 'action', name: 'widget_highlight', params: { target: '#unrelated' } },
    ]));
    expect(actions.map((action) => action.type)).toEqual(['speech', 'widget_highlight', 'widget_setState']);
    expect(actions[2]).toMatchObject({ state: { voltage: 9 } });
  });
});

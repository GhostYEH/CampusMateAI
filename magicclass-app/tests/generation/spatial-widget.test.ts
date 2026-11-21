import { describe, expect, it, vi } from 'vitest';
import { generateSceneActions, generateSceneContent } from '@magicclass/generation';
import type { SceneOutline } from '@/lib/types/generation';

const outline: SceneOutline = {
  id: 'solid-observation',
  order: 0,
  type: 'interactive',
  title: 'Observing cylinders and cones',
  description: 'Rotate and compare two solid shapes.',
  keyPoints: ['The solids share a base radius and height.'],
  widgetType: 'visualization3d',
  widgetOutline: { visualizationType: 'geometry', objects: ['Cylinder', 'Cone'] },
};

const shape = {
  id: 'cone_a',
  type: 'cone',
  name: 'Cone',
  material: { color: '#DAB27A' },
  animation: { type: 'rotate', axis: 'y', speed: 0.6 },
};
const description = 'Observe the curved surface. </script><script>alert("unsafe")</script>';

describe('spatial widgets generated from the same data for two players', () => {
  it('validates a compact model response and serializes the same scene into the browser runtime', async () => {
    const model = vi.fn(async () => JSON.stringify({ description, objects: [shape] }));
    const content = await generateSceneContent(outline, model);
    expect(model).toHaveBeenCalledTimes(1);
    expect(content).toMatchObject({
      widgetType: 'visualization3d',
      widgetConfig: { nativeRenderer: 'classroom-spatial/1', description, objects: [shape] },
    });
    if (!content || !('html' in content)) throw new Error('Expected an interactive scene');
    const json = /id="widget-config">([\s\S]*?)<\/script>/.exec(content.html)?.[1];
    expect(json).toBeTruthy();
    expect(JSON.parse(json!)).toEqual(content.widgetConfig);
    expect(content.html).not.toContain('</script><script>alert');
  });

  it.each([
    { requiresWebRuntime: true },
    { description: 'Invalid or unsupported solids', objects: [{ ...shape, type: 'custom' }] },
    { description: 'Duplicate IDs', objects: [shape, shape] },
  ])('retains the specialized browser generation when local content is unavailable (%j)', async (modelData) => {
    const website = '<!DOCTYPE html><html><body><div id="specialized-control">Tools</div>' +
      '<script type="application/json" id="widget-config">{"type":"visualization3d","nativeRenderer":"classroom-spatial/1"}</script></body></html>';
    const model = vi.fn<() => Promise<string>>()
      .mockResolvedValueOnce(JSON.stringify(modelData))
      .mockResolvedValueOnce(website);
    const content = await generateSceneContent(outline, model);
    expect(model).toHaveBeenCalledTimes(2);
    expect(content).toMatchObject({ html: expect.stringContaining('specialized-control') });
    if (!content || !('html' in content)) throw new Error('Expected an interactive scene');
    expect(content.widgetConfig?.nativeRenderer).toBeUndefined();
  });

  it('keeps speech and normalizes object highlights without introducing browser-only controls', async () => {
    const nested = { ...shape, id: 'cylinder_b', type: 'cylinder', children: [shape] };
    const content = await generateSceneContent(outline, async () =>
      JSON.stringify({ description: 'Compare the two bodies.', objects: [nested] }),
    );
    if (!content || !('html' in content)) throw new Error('Expected an interactive scene');
    const actions = await generateSceneActions(outline, content, async () => JSON.stringify([
      { type: 'text', content: 'Look at the cone.' },
      { type: 'action', name: 'widget_highlight', params: { target: 'cone_a' } },
      { type: 'action', name: 'widget_highlight', params: { target: '#slider' } },
      { type: 'action', name: 'widget_setState', params: { state: { scale: 2 } } },
    ]));
    expect(actions.map((action) => action.type)).toEqual(['speech', 'widget_highlight']);
    expect(actions[1]).toMatchObject({ target: '#cone_a' });
  });
});

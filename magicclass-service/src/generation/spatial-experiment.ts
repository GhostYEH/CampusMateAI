import { spatialExperimentHtml } from './spatial-experiment-html.ts';

const PROFILE = 'classroom-spatial/1';
const SHAPES = ['box', 'sphere', 'cylinder', 'cone', 'torus', 'plane'];
const AXES = ['x', 'y', 'z'];

export const INLINE_SPATIAL_MARKER = '<meta name="campusmate-spatial-runtime" content="1">';

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function within(value: unknown, min: number, max: number): value is number {
  return typeof value === 'number' && Number.isFinite(value) && min <= value && value <= max;
}

function includes(values: readonly string[], value: unknown): value is string {
  return typeof value === 'string' && values.includes(value);
}

function vector(raw: unknown, min: number, max: number) {
  const value = record(raw);
  if (!value || !within(value.x, min, max) || !within(value.y, min, max) || !within(value.z, min, max)) return null;
  return { x: value.x, y: value.y, z: value.z };
}

function parseObject(raw: unknown, ids: Set<string>, depth: number): Record<string, unknown> | null {
  const value = record(raw);
  if (!value || depth > 3 || ids.size >= 16 || typeof value.id !== 'string' ||
      !/^[A-Za-z_][A-Za-z0-9_-]{0,63}$/.test(value.id) || ids.has(value.id) || !includes(SHAPES, value.type)) return null;
  const name = typeof value.name === 'string' ? value.name.trim() : '';
  if (!name || name.length > 80) return null;

  const appearance = record(value.material);
  if (!appearance || typeof appearance.color !== 'string' || !/^#[0-9a-f]{6}$/i.test(appearance.color) ||
      (appearance.wireframe !== undefined && typeof appearance.wireframe !== 'boolean') ||
      (appearance.transparent !== undefined && typeof appearance.transparent !== 'boolean') ||
      (appearance.opacity !== undefined && (!within(appearance.opacity, .15, 1) || (appearance.opacity < 1 && appearance.transparent !== true))) ||
      (appearance.type !== undefined && !includes(['standard', 'lambert', 'phong', 'basic', 'emissive'], appearance.type))) return null;
  const material = { color: appearance.color,
    ...(appearance.type !== undefined && { type: appearance.type }),
    ...(appearance.wireframe !== undefined && { wireframe: appearance.wireframe }),
    ...(appearance.transparent !== undefined && { transparent: appearance.transparent }),
    ...(appearance.opacity !== undefined && { opacity: appearance.opacity }),
  };

  const position = vector(value.position, -40, 40);
  const rotation = vector(value.rotation, -360, 360);
  const scale = within(value.scale, .03, 12) ? value.scale : vector(value.scale, .03, 12);
  if ((value.position !== undefined && !position) || (value.rotation !== undefined && !rotation) ||
      (value.scale !== undefined && scale === null)) return null;

  const motion = record(value.animation);
  if (value.animation !== undefined && (!motion || !includes(['rotate', 'orbit', 'bounce', 'pulse'], motion.type) ||
      (motion.axis !== undefined && !includes(AXES, motion.axis)) ||
      (motion.speed !== undefined && !within(motion.speed, .05, 6)))) return null;

  ids.add(value.id);
  const children: Record<string, unknown>[] = [];
  if (value.children !== undefined) {
    if (!Array.isArray(value.children) || value.children.length > 16) return null;
    for (const candidate of value.children) {
      const child = parseObject(candidate, ids, depth + 1);
      if (!child) return null;
      children.push(child);
    }
  }

  return { id: value.id, name, type: value.type, material,
    ...(position && { position }), ...(rotation && { rotation }), ...(scale !== null && { scale }),
    ...(motion && { animation: { type: motion.type, axis: motion.axis ?? 'y', speed: motion.speed ?? 1 } }),
    ...(children.length && { children }),
  };
}

export function materializeSpatialExperiment(raw: unknown): Record<string, unknown> | null {
  const value = record(raw);
  if (!value || (value.type !== undefined && value.type !== 'visualization3d') ||
      (value.nativeRenderer !== undefined && value.nativeRenderer !== PROFILE) ||
      !Array.isArray(value.objects) || !value.objects.length || value.objects.length > 16) return null;
  const description = typeof value.description === 'string' ? value.description.trim() : '';
  if (!description || description.length > 1500) return null;

  const ids = new Set<string>();
  const objects: Record<string, unknown>[] = [];
  for (const candidate of value.objects) {
    const object = parseObject(candidate, ids, 1);
    if (!object) return null;
    objects.push(object);
  }
  return { type: 'visualization3d', nativeRenderer: PROFILE, description, objects,
    interactions: [{ type: 'orbit', target: 'camera' }, { type: 'zoom', target: 'camera' }],
  };
}

export function renderSpatialExperiment(config: Record<string, unknown>): string {
  return spatialExperimentHtml(config, INLINE_SPATIAL_MARKER);
}

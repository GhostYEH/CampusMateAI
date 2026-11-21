import type { WidgetConfig } from './scene-types.js';

const PROFILE = 'classroom-spatial/1';
const SHAPES = ['box', 'sphere', 'cylinder', 'cone', 'torus', 'plane'] as const;
const MATERIALS = ['standard', 'lambert', 'phong', 'basic', 'emissive'];
const MOTIONS = ['rotate', 'orbit', 'bounce', 'pulse'];
const AXES = ['x', 'y', 'z'];
const OBJECT_ID = /^[A-Za-z_][A-Za-z0-9_-]{0,63}$/;

type Vector = { x: number; y: number; z: number };
type Solid = {
  id: string;
  name: string;
  type: (typeof SHAPES)[number];
  material: { color: string; type?: string; opacity?: number; transparent?: boolean; wireframe?: boolean };
  position?: Vector;
  rotation?: Vector;
  scale?: number | Vector;
  animation?: { type: string; axis?: string; speed?: number };
  children?: Solid[];
};

export interface SpatialWidget extends WidgetConfig {
  type: 'visualization3d';
  nativeRenderer: typeof PROFILE;
  visualizationType?: string;
  description: string;
  objects: Solid[];
  interactions: Array<{ type: 'orbit' | 'zoom'; target: 'camera' }>;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function hasOnly(value: Record<string, unknown>, fields: readonly string[]): boolean {
  return Object.keys(value).every((key) => fields.includes(key));
}

function bounded(value: unknown, min: number, max: number): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function vector(value: unknown, min: number, max: number): value is Vector {
  const xyz = record(value);
  return !!xyz && hasOnly(xyz, AXES) && AXES.every((axis) => bounded(xyz[axis], min, max));
}

function validMaterial(value: unknown): value is Solid['material'] {
  const item = record(value);
  return !!item &&
    hasOnly(item, ['color', 'type', 'wireframe', 'transparent', 'opacity']) &&
    typeof item.color === 'string' && /^#[0-9a-f]{6}$/i.test(item.color) &&
    (item.type === undefined || MATERIALS.includes(String(item.type)) && typeof item.type === 'string') &&
    (item.wireframe === undefined || typeof item.wireframe === 'boolean') &&
    (item.transparent === undefined || typeof item.transparent === 'boolean') &&
    (item.opacity === undefined || (bounded(item.opacity, 0.15, 1) && (item.opacity === 1 || item.transparent === true)));
}

function validMotion(value: unknown): value is NonNullable<Solid['animation']> {
  const item = record(value);
  return !!item && hasOnly(item, ['type', 'axis', 'speed']) &&
    typeof item.type === 'string' && MOTIONS.includes(item.type) &&
    (item.axis === undefined || typeof item.axis === 'string' && AXES.includes(item.axis)) &&
    (item.speed === undefined || bounded(item.speed, 0.05, 6));
}

function solid(value: unknown, ids: Set<string>, depth: number): value is Solid {
  if (depth > 3 || ids.size >= 16) return false;
  const item = record(value);
  if (!item || !hasOnly(item, ['id', 'name', 'type', 'material', 'position', 'rotation', 'scale', 'animation', 'children'])) return false;
  if (typeof item.id !== 'string' || !OBJECT_ID.test(item.id) || ids.has(item.id)) return false;
  if (typeof item.name !== 'string' || !item.name.trim() || item.name.trim().length > 80) return false;
  if (!SHAPES.some((shape) => shape === item.type) || !validMaterial(item.material)) return false;
  if (item.position !== undefined && !vector(item.position, -40, 40)) return false;
  if (item.rotation !== undefined && !vector(item.rotation, -360, 360)) return false;
  if (item.scale !== undefined && !bounded(item.scale, .03, 12) && !vector(item.scale, .03, 12)) return false;
  if (item.animation !== undefined && !validMotion(item.animation)) return false;
  ids.add(item.id);
  return item.children === undefined ||
    (Array.isArray(item.children) && item.children.length <= 16 && item.children.every((child: unknown) => solid(child, ids, depth + 1)));
}

export function materializeSpatialWidget(raw: unknown, visualizationType?: string): SpatialWidget | null {
  const value = record(raw);
  if (!value || !hasOnly(value, ['description', 'objects']) || typeof value.description !== 'string') return null;
  const description = value.description.trim();
  if (!description || description.length > 1500) return null;
  const objects = value.objects;
  if (!Array.isArray(objects) || objects.length < 1 || objects.length > 16) return null;
  const ids = new Set<string>();
  if (!objects.every((item: unknown): item is Solid => solid(item, ids, 1))) return null;
  return {
    type: 'visualization3d',
    nativeRenderer: PROFILE,
    ...(visualizationType && { visualizationType }),
    description,
    objects,
    interactions: [{ type: 'orbit', target: 'camera' }, { type: 'zoom', target: 'camera' }],
  };
}

export function spatialObjectIds(config: WidgetConfig | undefined): Set<string> | null {
  if (config?.nativeRenderer !== PROFILE) return null;
  const verified = materializeSpatialWidget({ description: config.description, objects: config.objects });
  if (!verified) return null;
  const ids = new Set<string>();
  function add(objects: Solid[]) {
    for (const object of objects) {
      ids.add(object.id);
      if (object.children) add(object.children);
    }
  }
  add(verified.objects);
  return ids;
}

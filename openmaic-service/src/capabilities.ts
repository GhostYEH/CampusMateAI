/**
 * The complete vocabulary of capability tags this service may advertise.
 *
 * FastAPI only trusts names from this list, so a compromised or buggy service
 * cannot talk the browser into enabling an entry point that does not exist.
 * A tag appears in `/internal/health/ready` only when a mounted route module
 * declares it, which keeps the advertised set equal to the implemented set.
 */
export const KNOWN_CAPABILITIES = [
  'workspace',
  'stage-dsl',
  'editor',
  'player',
  'folder',
  'search',
  'material',
  'import-pptx',
  'import-maic',
  'export-maic',
  'export-pptx',
  'export-markdown',
  'export-docx',
  'export-video',
  'generation',
  'whiteboard',
  'tts',
  'multi-agent',
  'provider-status',
] as const;

export type Capability = (typeof KNOWN_CAPABILITIES)[number];

const KNOWN = new Set<string>(KNOWN_CAPABILITIES);

export function isKnownCapability(value: unknown): value is Capability {
  return typeof value === 'string' && KNOWN.has(value);
}

/** Stable ordering so readiness payloads are diffable across deploys. */
export function normalizeCapabilities(values: Iterable<string>): Capability[] {
  const seen = new Set<Capability>();
  for (const value of values) {
    if (isKnownCapability(value)) seen.add(value);
  }
  return KNOWN_CAPABILITIES.filter((capability) => seen.has(capability));
}

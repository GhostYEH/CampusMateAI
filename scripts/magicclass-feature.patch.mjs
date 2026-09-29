/**
 * Load the reviewed snapshot/hunk manifest that records approved functional
 * changes. Paths are relative to magicclass-app after branding; the manifest
 * contents are the only additional source of truth besides the upstream tree.
 */
import { readFileSync } from 'node:fs';

const patch = JSON.parse(readFileSync(new URL('./magicclass-feature.edits.json', import.meta.url), 'utf8'));

export const FEATURE_EDITS = patch.edits;
export const FEATURE_ADDED_FILES = patch.addedFiles;

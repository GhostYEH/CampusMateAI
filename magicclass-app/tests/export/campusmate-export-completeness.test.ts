import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Scene, Stage } from '@/lib/types/stage';

const mocks = vi.hoisted(() => ({
  entries: [] as { ref: string; kind: string }[],
  legacy: vi.fn(),
}));
vi.mock('@/lib/store/stage', () => ({ useStageStore: { getState: vi.fn() } }));
vi.mock('@/lib/document-store', () => ({ accessDocument: async () => ({ document: null }) }));
vi.mock('@/lib/pbl/v2/runtime/document-persistence', () => ({
  preparePBLScenesForDocumentPersistence: async (_id: string, scenes: Scene[]) => scenes,
}));
vi.mock('@/lib/media/asset-manifest', () => ({
  buildStageAssetManifest: async () => ({ entries: mocks.entries }),
}));
vi.mock('@/lib/export/classroom-zip-utils', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/export/classroom-zip-utils')>();
  return {
    ...actual,
    collectAudioFiles: async () => [],
    collectMediaFiles: async () => [],
    collectLegacyAudioForExport: mocks.legacy,
  };
});

import { buildClassroomExportZip } from '@/lib/export/use-export-classroom';

const stage = {
  id: 'shared',
  name: 'Complete shared classroom',
  createdAt: 1,
  updatedAt: 1,
} as Stage;
function scenes(audio: Record<string, string> = {}): Scene[] {
  return [
    {
      id: 'scene',
      stageId: 'shared',
      type: 'quiz',
      title: 'Quiz',
      order: 0,
      content: { type: 'quiz', questions: [] },
      actions: [{ id: 'speech', type: 'speech', text: 'Hello', ...audio }],
    },
  ] as unknown as Scene[];
}
afterEach(() => {
  mocks.entries = [];
  mocks.legacy.mockReset();
});

describe('shared classroom archives require referenced resource bytes', () => {
  it('rejects an image that the normal exporter would silently omit', async () => {
    mocks.entries = [{ ref: 'pending-image', kind: 'image' }];
    mocks.legacy.mockResolvedValue({ audioUrlToPath: new Map(), blobs: [] });
    await expect(
      buildClassroomExportZip(stage, scenes(), {}, { requireCompleteAssets: true }),
    ).rejects.toThrow('尚未就绪');
  });

  it('allows a missing audio ID when the legacy URL supplies actual archive bytes', async () => {
    const url = 'https://media.example.edu/narration.mp3';
    const zipPath = 'audio/legacy-1.mp3';
    mocks.entries = [{ ref: 'evicted-audio', kind: 'audio' }];
    mocks.legacy.mockResolvedValue({
      audioUrlToPath: new Map([[url, zipPath]]),
      blobs: [
        {
          sourceRef: url,
          zipPath,
          blob: new TextEncoder().encode('narration'),
          mimeType: 'audio/mpeg',
          format: 'mp3',
        },
      ],
    });
    const output = await buildClassroomExportZip(
      stage,
      scenes({ audioId: 'evicted-audio', audioUrl: url }),
      {},
      { requireCompleteAssets: true },
    );
    const JSZip = (await import('jszip')).default;
    const zip = await JSZip.loadAsync(await output.zip.arrayBuffer());
    const manifest = JSON.parse(await zip.file('manifest.json')!.async('text'));
    expect(manifest.scenes[0].actions[0].audioRef).toBe(zipPath);
    expect(await zip.file(zipPath)!.async('text')).toBe('narration');
  });

  it('rejects lost URL-only narration while allowing speech that never had audio', async () => {
    mocks.legacy.mockResolvedValue({ audioUrlToPath: new Map(), blobs: [] });
    await expect(
      buildClassroomExportZip(
        stage,
        scenes({ audioUrl: 'https://media.example.edu/missing.mp3' }),
        {},
        { requireCompleteAssets: true },
      ),
    ).rejects.toThrow('语音尚未就绪');
    await expect(
      buildClassroomExportZip(stage, scenes(), {}, { requireCompleteAssets: true }),
    ).resolves.toHaveProperty('zip');
  });
});

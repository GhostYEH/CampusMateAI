'use client';

import { useCallback, useEffect, useRef } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  CAMPUSMATE_CHANNEL,
  campusmateParentOrigin,
  classroomMediaStatus,
} from '@/lib/classroom/campusmate-entry';
import { useStageStore } from '@/lib/store/stage';
import { useMediaGenerationStore } from '@/lib/store/media-generation';
import { useImportClassroom } from '@/lib/import/use-import-classroom';

/** Reuses the portable classroom format so media never points at another device's blobs. */
export function CampusmateLearningBridge() {
  const router = useRouter();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  const busy = useRef(false);
  const { importFile } = useImportClassroom();
  const send = useCallback((type: string, data: Record<string, unknown> = {}) => {
    const origin = campusmateParentOrigin();
    if (origin) window.parent.postMessage({ channel: CAMPUSMATE_CHANNEL, type, ...data }, origin);
  }, []);

  useEffect(() => {
    const origin = campusmateParentOrigin();
    if (!origin) return;
    sessionStorage.setItem('campusmate-parent-origin', origin);
    pathnameRef.current = pathname;
    let last = '';
    const publish = () => {
      const s = useStageStore.getState();
      const inClassroom = pathnameRef.current.startsWith('/classroom/');
      const media = classroomMediaStatus(s.stage?.id, useMediaGenerationStore.getState().tasks);
      const state = {
        stageId: inClassroom ? (s.stage?.id ?? null) : null,
        title: s.stage?.name ?? '',
        complete:
          s.generationComplete &&
          s.generatingOutlines.length === 0 &&
          s.scenes.length > 0 &&
          !media.pending &&
          !media.failed,
        mediaFailed: media.failed,
        sceneIndex: Math.max(
          0,
          s.scenes.findIndex((scene) => scene.id === s.currentSceneId),
        ),
      };
      const serialized = JSON.stringify(state);
      if (serialized !== last) {
        last = serialized;
        send('state', state);
      }
    };
    send('ready');
    publish();
    const unsubscribe = useStageStore.subscribe(publish);
    const unsubscribeMedia = useMediaGenerationStore.subscribe(publish);
    return () => {
      unsubscribe();
      unsubscribeMedia();
    };
  }, [pathname, send]);

  useEffect(() => {
    const receive = async (event: MessageEvent) => {
      const origin = campusmateParentOrigin();
      if (
        !origin ||
        event.source !== window.parent ||
        event.origin !== origin ||
        event.data?.channel !== CAMPUSMATE_CHANNEL
      )
        return;
      const { type, requestId } = event.data;
      if (type === 'cursor') {
        const s = useStageStore.getState();
        if (s.stage?.id !== event.data.stageId) return;
        const scene = s.scenes[event.data.sceneIndex];
        if (scene && s.currentSceneId !== scene.id) s.setCurrentSceneId(scene.id);
        return;
      }
      if (type === 'home') {
        router.push('/');
        return;
      }
      if (type !== 'export' && type !== 'import') return;
      if (busy.current) {
        send('result', { requestId, error: '课堂正在准备，请稍后重试' });
        return;
      }
      busy.current = true;
      try {
        if (type === 'export') {
          const s = useStageStore.getState();
          const media = classroomMediaStatus(s.stage?.id, useMediaGenerationStore.getState().tasks);
          if (
            !s.stage ||
            s.stage.id !== event.data.stageId ||
            !s.generationComplete ||
            !s.scenes.length ||
            media.pending ||
            media.failed
          ) {
            throw new Error('请等待课堂生成完成后再邀请');
          }
          await s.saveToStorage();
          const { buildClassroomExportZip } = await import('@/lib/export/use-export-classroom');
          const result = await buildClassroomExportZip(
            s.stage,
            s.scenes,
            {},
            { requireCompleteAssets: true },
          );
          if (result.zip.size > 64 * 1024 * 1024) throw new Error('共同课堂文件不能超过 64 MB');
          if (result.inlineFailures.length) throw new Error('部分课堂资源暂时无法读取，请稍后重试');
          send('result', {
            requestId,
            archive: result.zip,
            title: s.stage.name,
            stageId: s.stage.id,
          });
        } else {
          if (!(event.data.archive instanceof Blob) || event.data.archive.size > 64 * 1024 * 1024) {
            throw new Error('课堂文件无效或过大');
          }
          const sceneIndex =
            Number.isInteger(event.data.sceneIndex) && event.data.sceneIndex >= 0
              ? event.data.sceneIndex
              : 0;
          const stageId = await importFile(
            new File([event.data.archive], 'shared.maic.zip', { type: 'application/zip' }),
            { initialSceneIndex: sceneIndex },
          );
          if (!stageId) throw new Error('共同课堂加载失败，请重试');
          send('result', { requestId, stageId });
          router.push(`/classroom/${stageId}`);
        }
      } catch (error) {
        send('result', {
          requestId,
          error: error instanceof Error ? error.message : '课堂准备失败',
        });
      } finally {
        busy.current = false;
      }
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [router, importFile, send]);
  return null;
}

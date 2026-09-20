import type { ProviderConfig, RenderConfig, TtsConfig } from '../config.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { DslLimitError } from '../dsl/limits.ts';
import { DslValidationError, prepareStage } from '../dsl/validate.ts';
import { DslVersionError } from '../dsl/version.ts';
import { isGenerationMode, materializeGeneratedStage } from '../generation/generator.ts';
import type { JobRepository } from '../jobs/repository.ts';
import type { WorkspaceRepository } from '../workspace/repository.ts';
import {
  ProviderError,
  generateStageDocument,
  runDiscussion,
  synthesizeSpeech,
  type ProviderErrorCode,
  renderStageToMp4,
} from './client.ts';
import { narrationFilename } from '../tts/scene-narration-routes.ts';

/**
 * Provider work cannot run inside a route handler: handlers are synchronous on
 * purpose (jti + writes share one SQLite transaction). Queued jobs are the
 * bridge — the handler enqueues, this worker claims and runs the upstream call
 * asynchronously, and clients poll the job until it completes.
 */
export interface QueuedJobRef {
  id: string;
  user_id: string;
  course_id: string;
  kind: string;
}

export interface ProviderJobWorker {
  start(): void;
  stop(): Promise<void>;
  /** Claim and process at most one queued job. Resolves true when it did. */
  tick(): Promise<boolean>;
}

const POLLABLE_KINDS = "('generation', 'tts', 'discussion', 'video')";

function classify(error: unknown): ProviderErrorCode {
  if (error instanceof ProviderError) return error.code;
  if (error instanceof DslValidationError || error instanceof DslLimitError || error instanceof DslVersionError) {
    return 'provider_invalid_response';
  }
  return 'internal_error';
}

function safeFilename(title: string, fallback: string): string {
  // eslint-disable-next-line no-control-regex
  const cleaned = title.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '').trim().slice(0, 60);
  return cleaned || fallback;
}

export function createProviderJobWorker(options: {
  database: ServiceDatabase;
  jobs: JobRepository;
  workspaces: WorkspaceRepository;
  provider?: ProviderConfig;
  tts?: TtsConfig;
  render?: RenderConfig;
  pollIntervalMs?: number;
  now?: () => string;
}): ProviderJobWorker {
  const { database, jobs, workspaces } = options;
  const now = options.now ?? (() => new Date().toISOString());
  let timer: ReturnType<typeof setInterval> | undefined;
  let inFlight = false;
  let stopped = false;

  function claimNext(): QueuedJobRef | null {
    return database.transaction(() => {
      const row = database.raw.prepare(
        `SELECT id, user_id, course_id, kind FROM jobs
          WHERE status = 'queued' AND kind IN ${POLLABLE_KINDS}
          ORDER BY created_at, id LIMIT 1`,
      ).get() as QueuedJobRef | undefined;
      if (!row) return null;
      try {
        const claimed = jobs.markRunning({ jobId: row.id, userId: row.user_id, courseId: row.course_id, now: now() });
        if (claimed.status !== 'running') return null;
      } catch {
        return null;
      }
      return row;
    });
  }

  async function runGeneration(identity: { userId: string; courseId: string; jobId: string }, input: Record<string, unknown>): Promise<void> {
    if (!options.provider) throw new ProviderError('provider_rejected', 'generation provider is not configured');
    const mode = typeof input.mode === 'string' ? input.mode : '';
    const prompt = typeof input.prompt === 'string' ? input.prompt.trim() : '';
    const workspaceId = typeof input.workspace_id === 'string' ? input.workspace_id : '';
    if (!isGenerationMode(mode) || !prompt || !workspaceId) {
      throw new ProviderError('internal_error', 'generation job input is incomplete');
    }
    const agentIds = input.role_mode === 'preset' && Array.isArray(input.selected_role_ids)
      ? [...new Set(input.selected_role_ids
        .filter((value): value is string => typeof value === 'string' && value.trim())
        .map((value) => value.trim()))].slice(0, 7)
      : [];
    const raw = await generateStageDocument(options.provider, { mode, prompt });
    const prepared = prepareStage(materializeGeneratedStage(raw, { agentIds, mode, prompt }));
    const title = String(prepared.document.stage?.name ?? prompt).slice(0, 200);
    workspaces.createStage({
      userId: identity.userId,
      courseId: identity.courseId,
      workspaceId,
      title,
      document: prepared.document,
      dslVersion: prepared.document.dslVersion,
      now: now(),
    });
    jobs.complete({
      ...identity,
      artifact: {
        filename: `${safeFilename(title, '学习内容')}.stage.json`,
        mediaType: 'application/json',
        payload: Buffer.from(JSON.stringify(prepared.document), 'utf8'),
      },
      now: now(),
    });
  }

  async function runTts(identity: { userId: string; courseId: string; jobId: string }, input: Record<string, unknown>): Promise<void> {
    if (!options.tts) throw new ProviderError('provider_rejected', 'tts provider is not configured');
    const text = typeof input.text === 'string' ? input.text.trim() : '';
    if (!text) throw new ProviderError('internal_error', 'tts job input is incomplete');
    const wav = await synthesizeSpeech(options.tts, {
      text,
      instruction: typeof input.instruction === 'string' ? input.instruction : undefined,
      voice: typeof input.voice === 'string' ? input.voice : undefined,
    });
    // 文件名如实反映这份音频是什么：
    // - 绑定了场景的（scene_id + scene_title）是**该场景的讲解**，带页名与短 id，
    //   在产物列表里一眼能看出归属，也不会与别页混淆；
    // - 没绑定场景的仍是自由文本合成（既有 `/tts` 路径），如实叫"语音合成"，
    //   不再冒充"讲解音频"。
    const sceneId = typeof input.scene_id === 'string' ? input.scene_id : '';
    const sceneTitle = typeof input.scene_title === 'string' ? input.scene_title : '';
    const filename = sceneId
      ? narrationFilename(sceneTitle, sceneId)
      : `${safeFilename(text.slice(0, 40), '语音合成')}.wav`;
    jobs.complete({
      ...identity,
      artifact: { filename, mediaType: 'audio/wav', payload: wav },
      now: now(),
    });
  }

  async function runDiscussionJob(identity: { userId: string; courseId: string; jobId: string }, input: Record<string, unknown>): Promise<void> {
    if (!options.provider) throw new ProviderError('provider_rejected', 'discussion provider is not configured');
    const prompt = typeof input.prompt === 'string' ? input.prompt.trim() : '';
    if (!prompt) throw new ProviderError('internal_error', 'discussion job input is incomplete');
    const messages = await runDiscussion(options.provider, { prompt });
    jobs.complete({
      ...identity,
      artifact: {
        filename: '圆桌讨论.json',
        mediaType: 'application/json',
        payload: Buffer.from(JSON.stringify({ messages }), 'utf8'),
      },
      now: now(),
    });
  }

  async function runVideo(identity: { userId: string; courseId: string; jobId: string }, input: Record<string, unknown>): Promise<void> {
    if (!options.render) throw new ProviderError('provider_rejected', 'render service is not configured');
    const workspaceId = typeof input.workspace_id === 'string' ? input.workspace_id : '';
    const stageId = typeof input.stage_id === 'string' ? input.stage_id : '';
    if (!workspaceId || !stageId) throw new ProviderError('internal_error', 'video job input is incomplete');
    const stage = workspaces.getStage({ userId: identity.userId, courseId: identity.courseId, workspaceId, stageId });
    const video = await renderStageToMp4(options.render, stage.document);
    const title = safeFilename(stage.title, '学习内容');
    jobs.complete({
      ...identity,
      artifact: { filename: `${title}.mp4`, mediaType: 'video/mp4', payload: video },
      now: now(),
    });
  }

  async function processJob(ref: QueuedJobRef): Promise<void> {
    const identity = { userId: ref.user_id, courseId: ref.course_id, jobId: ref.id };
    try {
      const job = jobs.get(identity);
      let input: Record<string, unknown>;
      try {
        input = JSON.parse(job.input_json ?? '{}') as Record<string, unknown>;
      } catch {
        throw new ProviderError('internal_error', 'job input is not valid JSON');
      }
      if (ref.kind === 'generation') await runGeneration(identity, input);
      else if (ref.kind === 'tts') await runTts(identity, input);
      else if (ref.kind === 'discussion') await runDiscussionJob(identity, input);
      else if (ref.kind === 'video') await runVideo(identity, input);
      else jobs.fail({ ...identity, errorCode: 'internal_error', now: now() });
    } catch (error) {
      try {
        jobs.fail({ ...identity, errorCode: classify(error), now: now() });
      } catch {
        // The job vanished (e.g. hard delete); nothing left to mark.
      }
    }
  }

  async function tick(): Promise<boolean> {
    if (inFlight || stopped) return false;
    inFlight = true;
    try {
      const ref = claimNext();
      if (!ref) return false;
      await processJob(ref);
      return true;
    } finally {
      inFlight = false;
    }
  }

  return {
    start(): void {
      stopped = false;
      timer = setInterval(() => {
        void tick();
      }, options.pollIntervalMs ?? 500);
    },
    async stop(): Promise<void> {
      stopped = true;
      if (timer) {
        clearInterval(timer);
        timer = undefined;
      }
      while (inFlight) {
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
    },
    tick,
  };
}

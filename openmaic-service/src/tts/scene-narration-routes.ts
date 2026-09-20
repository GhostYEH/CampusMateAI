/**
 * 场景讲解音频 —— 按场景、按需生成。
 *
 * ## 为什么是独立的 route 模块而不是扩展 `/tts`
 *
 * `/internal/courses/:courseId/tts` 已经是既有契约（自由文本 → 音频），Web 端和
 * 后端网关都在用。把"按场景生成讲解"塞进同一个端点会改变它的语义，也会让
 * 既有调用方传 `text` 的行为变得可疑。所以这里**新增**两个端点，`/tts` 原样保留：
 *
 *   POST /internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/scenes/:sceneId/narration
 *   GET  /internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/scenes/:sceneId/narration
 *
 * 路径层级刻意与既有 route 完全一致（workspace → stage → scene）：舞台文档的
 * 所有权检查由 `WorkspaceRepository.getStage` 的 WHERE 子句给出，不需要新写一条
 * "按 stageId 反查 workspace"的旁路，也就不会多出一处可能漏掉 course_id 的地方。
 *
 * ## 讲稿从哪来
 *
 * **服务端**从场景正文派生（`tts/narration.ts`），客户端只给 sceneId。这堵住了
 * 之前那条缺陷：客户端传什么文本、就合成什么音频，音频和任何一页都没有关系。
 * 现在"这一页的音频"由"这一页的内容"唯一决定。
 *
 * ## 重复点击怎么处理
 *
 * 三层，缺一层都会漏：
 *
 * 1. **已完成且讲稿未变 → 直接复用**，连任务都不建（最常见的重复点击）；
 * 2. **正在排队/运行 → 复用同一个 job**，不再排第二个；
 * 3. **`Idempotency-Key`** 兜住同一请求的重放，语义与其它写端点一致。
 *
 * 三者都返回同一个 job，所以重复点击不会产生多份音频，也不会多次计费。
 */

import type { Capability } from '../capabilities.ts';
import type { TtsConfig } from '../config.ts';
import type { ServiceDatabase } from '../db/database.ts';
import { IdempotencyStore } from '../db/idempotencyStore.ts';
import type { Scene } from '../dsl/contract.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { JobRepository } from '../jobs/repository.ts';
import { jobResponse } from '../jobs/routes.ts';
import type { WorkspaceRepository } from '../workspace/repository.ts';
import { hashRequest } from '../workspace/repository.ts';
import { IDEMPOTENCY_HEADER } from '../workspace/routes.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { buildSceneNarration, narrationFingerprint } from './narration.ts';

export const NARRATION_SCOPE = 'tts:write';
export const NARRATION_READ_SCOPE = 'tts:read';
export const NARRATION_CAPABILITY: Capability = 'tts';

/** 讲解音频的文件名。带 sceneId，便于在产物列表里一眼看出归属。 */
export function narrationFilename(sceneTitle: string, sceneId: string): string {
  // eslint-disable-next-line no-control-regex
  const cleaned = sceneTitle.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '').trim().slice(0, 40);
  const suffix = sceneId.slice(-6);
  return `${cleaned || '讲解'}-${suffix}.wav`;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * 从舞台文档里取出一个场景**用于讲稿的字段**。
 *
 * 只回传 `type/title/content` 三项：`buildSceneNarration` 只需要这些，而少传一项
 * 就少一条"讲稿里混进内部字段"的路径。
 */
export function selectNarrationScene(document: unknown, sceneId: string): Pick<Scene, 'type' | 'title' | 'content'> {
  const scenes = isObject(document) && Array.isArray(document.scenes) ? document.scenes : [];
  for (const entry of scenes) {
    if (!isObject(entry) || entry.id !== sceneId) continue;
    const type = typeof entry.type === 'string' ? entry.type : '';
    const title = typeof entry.title === 'string' ? entry.title : '';
    if (!type) break;
    return { type, title, content: entry.content } as Pick<Scene, 'type' | 'title' | 'content'>;
  }
  throw new WorkspaceError('not_found', 'scene not found in this stage');
}

export function createSceneNarrationRoutes(options: {
  database: ServiceDatabase;
  workspaces: WorkspaceRepository;
  tts?: TtsConfig;
  available?: boolean;
  now?: () => string;
}): RouteDefinition[] {
  const available = options.available ?? Boolean(options.tts);
  const jobs = new JobRepository(options.database);
  const idempotency = new IdempotencyStore(options.database);
  const now = options.now ?? (() => new Date().toISOString());

  const pattern = '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/scenes/:sceneId/narration';

  return [
    {
      method: 'GET', pattern, scopes: [NARRATION_READ_SCOPE], courseScoped: true,
      capabilities: available ? [NARRATION_CAPABILITY] : [],
      handler: (request): RouteResponse => {
        try {
          const who = identity(request);
          const { userId, courseId, stageId, sceneId } = who;
          // 先确认场景真的属于这个舞台：否则"读音频"会变成一条越过课程内容
          // 直接问"有没有这个 id 的产物"的旁路。
          const document = readDocument(options.workspaces, who);
          const scene = selectNarrationScene(document, sceneId);
          const draft = buildSceneNarration(scene);
          const hash = draft.text ? narrationFingerprint(sceneId, draft.text) : null;

          const existing = hash
            ? jobs.findCompletedSceneNarration({ userId, courseId, sceneId, narrationHash: hash })
            : null;
          const active = jobs.findActiveSceneNarration({ userId, courseId, sceneId });

          return {
            status: 200,
            body: {
              scene_id: sceneId,
              stage_id: stageId,
              available,
              // 讲稿是否为空由服务端如实回答，客户端据此显示"这一页没有可讲解
              // 的文字"，而不是放一个点了永远失败的按钮。
              has_script: Boolean(draft.text),
              script_chars: draft.text.length,
              truncated: draft.truncated,
              // 讲稿变化会让已有音频失效（例如用户改了这一页的文字）。
              stale: Boolean(existing) && hash !== null && existing.narration_hash !== hash,
              job: existing ? jobResponse(existing) : active ? jobResponse(active) : null,
            },
          };
        } catch (error) {
          if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
          throw error;
        }
      },
    },
    {
      method: 'POST', pattern, scopes: [NARRATION_SCOPE], courseScoped: true,
      capabilities: available ? [NARRATION_CAPABILITY] : [],
      handler: (request): RouteResponse => {
        try {
          const who = identity(request);
          const { userId, courseId, stageId, sceneId } = who;
          const key = request.headers[IDEMPOTENCY_HEADER]?.trim();
          if (!key) throw new WorkspaceError('invalid_request', 'Idempotency-Key is required for this request');
          if (key.length > 200) throw new WorkspaceError('invalid_request', 'Idempotency-Key is too long');

          const document = readDocument(options.workspaces, who);
          const scene = selectNarrationScene(document, sceneId);
          const draft = buildSceneNarration(scene);

          if (!draft.text) {
            // 空讲稿不是"合成失败"，而是这一页确实没有可朗读的文字。如实回报，
            // 且**不建任务**——建了就会白跑一次上游。
            return {
              status: 200,
              body: { scene_id: sceneId, has_script: false, reuse: false, job: null, message: '这一页没有可讲解的文字' },
            };
          }

          const hash = narrationFingerprint(sceneId, draft.text);
          const body = { scene_id: sceneId, stage_id: stageId };
          const requestHash = hashRequest(body);
          const replay = idempotency.lookup(userId, key, requestHash);
          if (replay) return replay;

          if (!available || !options.tts) {
            return { status: 503, body: { error: 'provider_unavailable', message: 'tts provider is unavailable' } };
          }

          // 1) 讲稿没变且已有成品 → 复用，连任务都不建。
          const done = jobs.findCompletedSceneNarration({ userId, courseId, sceneId, narrationHash: hash });
          if (done) {
            const response: RouteResponse = {
              status: 200,
              body: { scene_id: sceneId, has_script: true, reuse: true, job: jobResponse(done) },
            };
            idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
            return response;
          }

          // 2) 已有在飞任务 → 复用同一个 job，不再排第二个。
          const active = jobs.findActiveSceneNarration({ userId, courseId, sceneId });
          if (active) {
            const response: RouteResponse = {
              status: 200,
              body: { scene_id: sceneId, has_script: true, reuse: true, job: jobResponse(active) },
            };
            idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
            return response;
          }

          // 3) 真正建任务。voice 由服务端配置决定（mimo-v2.5-tts 的预设音色），
          //    客户端不能指定任意字符串去影响上游计费模型。
          const job = jobs.create({
            userId, courseId, kind: 'tts', mode: options.tts.model,
            request: {
              // 讲稿存进任务，worker 只认这一份，不存在"提交时是一段、合成时是另一段"。
              text: draft.text,
              instruction: options.tts.voice ? `用${options.tts.voice}的声音，像老师讲课一样自然讲解。` : undefined,
              voice: options.tts.voice,
              scene_id: sceneId,
              scene_title: scene.title,
              stage_id: stageId,
              truncated: draft.truncated,
            },
            sceneId,
            narrationHash: hash,
            now: now(),
          });
          const response: RouteResponse = {
            status: 201,
            body: { scene_id: sceneId, has_script: true, reuse: false, job: jobResponse(job) },
          };
          idempotency.record(userId, key, { courseId, method: request.method, path: request.url.pathname }, requestHash, response);
          return response;
        } catch (error) {
          if (error instanceof WorkspaceError) return { status: error.status, body: { error: error.code, message: error.message } };
          throw error;
        }
      },
    },
  ];
}

function identity(request: RouteRequest) {
  return {
    userId: request.claims.sub,
    courseId: request.params.courseId ?? '',
    workspaceId: request.params.workspaceId ?? '',
    stageId: request.params.stageId ?? '',
    sceneId: request.params.sceneId ?? '',
  };
}

/**
 * 读舞台文档。所有权由 `getStage` 的 WHERE 子句（id + workspace_id + user_id +
 * course_id）保证：别人的舞台或别的课程会直接 404，不存在"先读到再判断"的窗口。
 */
function readDocument(
  workspaces: WorkspaceRepository,
  ids: { userId: string; courseId: string; workspaceId: string; stageId: string },
): unknown {
  const row = workspaces.getStage(ids);
  try {
    return JSON.parse(row.document);
  } catch {
    throw new WorkspaceError('invalid_request', 'stage document is not valid JSON');
  }
}

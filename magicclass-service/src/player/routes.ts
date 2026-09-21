/**
 * Internal playback route.
 *
 * The player is read-only: it serves a plan built from the stored document, so
 * the browser never receives a scene body it is not allowed to see, and the
 * sandbox decision is made server-side. `scene_id` carries the resume position so
 * a refresh reopens the scene the student stopped on instead of restarting.
 */

import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import type { StageAggregate } from '../dsl/contract.ts';
import { PlaybackError, buildPlaybackPlan, type RenderCapabilities } from './playback.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { WorkspaceRepository } from '../workspace/repository.ts';
import { STAGE_READ_SCOPE } from '../editor/routes.ts';

export const PLAYER_CAPABILITY: Capability = 'player';

function respond(work: () => RouteResponse): RouteResponse {
  try {
    return work();
  } catch (error) {
    // Ownership failures come from the repository, and they must keep their own
    // status: turning "not yours" into a 500 tells the caller to retry forever.
    if (error instanceof WorkspaceError) {
      return { status: error.status, body: { error: error.code, message: error.message } };
    }
    if (error instanceof PlaybackError) {
      return {
        status: error.code === 'scene_not_found' ? 404 : 400,
        body: { error: error.code, message: error.message },
      };
    }
    throw error;
  }
}

export interface PlayerRouteOptions {
  database: ServiceDatabase;
  /** Injected so a deployment can decide whether 3D content is renderable. */
  capabilities?: RenderCapabilities;
}

export function createPlayerRoutes(options: PlayerRouteOptions): RouteDefinition[] {
  const repository = new WorkspaceRepository(options.database);
  const capabilities = options.capabilities ?? { externalCdnAvailable: false };

  return [
    {
      method: 'GET',
      pattern: '/internal/courses/:courseId/workspaces/:workspaceId/stages/:stageId/playback',
      scopes: [STAGE_READ_SCOPE],
      courseScoped: true,
      capabilities: [PLAYER_CAPABILITY],
      handler: (request) => respond(() => {
        const row = repository.getStage({
          userId: request.claims.sub,
          courseId: request.params.courseId ?? '',
          workspaceId: request.params.workspaceId ?? '',
          stageId: request.params.stageId ?? '',
        });
        const document = JSON.parse(row.document) as StageAggregate;
        const plan = buildPlaybackPlan(
          document,
          {
            workspaceId: row.workspace_id,
            revision: Number(row.revision),
            dslVersion: row.dsl_version,
            startSceneId: request.url.searchParams.get('scene_id'),
          },
          capabilities,
        );
        return { status: 200, body: plan as unknown as Record<string, unknown> };
      }),
    },
  ];
}

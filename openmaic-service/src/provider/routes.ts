import type { Capability } from '../capabilities.ts';
import type { ServiceDatabase } from '../db/database.ts';
import type { RouteDefinition, RouteRequest, RouteResponse } from '../server.ts';

export const PROVIDER_STATUS_CAPABILITY: Capability = 'provider-status';

export interface ProviderAvailability {
  llm: boolean;
  webSearch: boolean;
  image: boolean;
  video: boolean;
  tts: boolean;
  render: boolean;
  external3d: boolean;
}

function publicStatus(value: ProviderAvailability): Record<string, boolean> {
  return { llm: value.llm, web_search: value.webSearch, image: value.image, video: value.video, tts: value.tts, render: value.render, external_3d: value.external3d };
}

export function createProviderRoutes(options: { database: ServiceDatabase; providers?: ProviderAvailability }): RouteDefinition[] {
  const providers = options.providers ?? { llm: false, webSearch: false, image: false, video: false, tts: false, render: false, external3d: false };
  return [{
    method: 'GET', pattern: '/internal/settings/providers', scopes: ['service:status'], courseScoped: false, capabilities: [PROVIDER_STATUS_CAPABILITY],
    handler: (_request: RouteRequest): RouteResponse => ({ status: 200, body: publicStatus(providers) }),
  }];
}

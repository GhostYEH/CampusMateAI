import type { ReplayStore, ServiceAssertionClaims } from '../serviceAssertion.ts';
import { ServiceAssertionError, verifyServiceAssertion } from '../serviceAssertion.ts';

export interface AuthorizeRequest {
  /** Raw assertion from `X-CampusMate-Service-Assertion`, already trimmed. */
  token: string | undefined;
  requiredScopes: string[];
  /**
   * The course the route claims to act on. For course-scoped routes this is the
   * `:courseId` path segment, so a valid assertion minted for course A can never
   * be replayed against course B.
   */
  expectedCourseId: string;
  now?: number;
}

/**
 * The single place internal requests become trusted. Route handlers never see an
 * unverified assertion, and verification failures never reach the client with
 * anything more specific than an opaque error code.
 */
export class ServiceAuthenticator {
  readonly #secret: string;
  readonly #replayStore: ReplayStore;
  readonly #now: () => number;

  constructor(options: { secret: string; replayStore: ReplayStore; now?: () => number }) {
    if (!options.secret) {
      throw new ServiceAssertionError('MAGICCLASS_INTERNAL_SECRET is not configured');
    }
    this.#secret = options.secret;
    this.#replayStore = options.replayStore;
    this.#now = options.now ?? (() => Math.floor(Date.now() / 1000));
  }

  authorize(request: AuthorizeRequest): ServiceAssertionClaims {
    if (!request.token) throw new ServiceAssertionError('assertion is missing');
    return verifyServiceAssertion(
      request.token,
      request.expectedCourseId,
      request.requiredScopes,
      request.now ?? this.#now(),
      { secret: this.#secret, replayStore: this.#replayStore },
    );
  }
}

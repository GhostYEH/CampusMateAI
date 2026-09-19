import { createHmac, timingSafeEqual } from 'node:crypto';

export const ISSUER = 'campusmate-backend';
export const AUDIENCE = 'openmaic-service';

/**
 * An assertion is a single-use capability for one user, one course and one
 * scope set. The window is deliberately tiny: a leaked assertion is only useful
 * until the next request consumes its jti.
 */
export const MAX_ASSERTION_TTL_SECONDS = 60;

export type ServiceAssertionClaims = {
  iss: string;
  aud: string;
  sub: string;
  course_id: string;
  scope: string[];
  iat: number;
  exp: number;
  jti: string;
};

/**
 * Machine-readable failure reasons. The HTTP layer maps these to status codes
 * and emits only the code, never the human-readable message, so a caller cannot
 * probe signature material or the expected audience.
 */
export type ServiceAssertionErrorCode =
  | 'assertion_missing'
  | 'assertion_malformed'
  | 'assertion_header'
  | 'assertion_signature'
  | 'assertion_audience'
  | 'assertion_course'
  | 'assertion_scope'
  | 'assertion_incomplete'
  | 'assertion_lifetime'
  | 'assertion_expired'
  | 'assertion_not_yet_valid'
  | 'assertion_replay';

export class ServiceAssertionError extends Error {
  readonly code: ServiceAssertionErrorCode;

  constructor(message: string, code: ServiceAssertionErrorCode = 'assertion_malformed') {
    super(message);
    this.name = 'ServiceAssertionError';
    this.code = code;
  }
}

export interface ConsumedAssertionRecord {
  jti: string;
  issuer: string;
  audience: string;
  subject: string;
  courseId: string;
  scopes: string[];
  issuedAt: number;
  expiresAt: number;
  consumedAt: number;
}

export interface ReplayStore {
  consume(record: ConsumedAssertionRecord): void;
}

/** Test double. Production wiring uses the SQLite-backed store in `./db`. */
export class InMemoryReplayStore implements ReplayStore {
  #used = new Map<string, number>();

  consume(record: ConsumedAssertionRecord) {
    for (const [usedJti, expiresAt] of this.#used) {
      if (expiresAt <= record.consumedAt) this.#used.delete(usedJti);
    }
    if (this.#used.has(record.jti)) {
      throw new ServiceAssertionError('assertion replay detected', 'assertion_replay');
    }
    this.#used.set(record.jti, record.expiresAt);
  }
}

function decodeBase64Url(value: string) {
  return Buffer.from(value, 'base64url').toString('utf8');
}

function secretFrom(options: VerifyOptions) {
  const secret = options.secret ?? process.env.OPENMAIC_INTERNAL_SECRET;
  if (!secret) {
    throw new ServiceAssertionError('OPENMAIC_INTERNAL_SECRET is not configured', 'assertion_missing');
  }
  return secret;
}

export type VerifyOptions = {
  secret?: string;
  replayStore?: ReplayStore;
  maxTtlSeconds?: number;
};

export function verifyServiceAssertion(
  token: string,
  /**
   * The course the route acts on. `null` means the route is not course-scoped
   * (health, provider status) and the claim is deliberately not compared.
   */
  expectedCourseId: string | null,
  requiredScopes: string[],
  now: number,
  options: VerifyOptions = {},
): ServiceAssertionClaims {
  const parts = token.split('.');
  if (parts.length !== 3) throw new ServiceAssertionError('malformed assertion');
  const [headerPart, bodyPart, signaturePart] = parts;
  let header: unknown;
  let claims: Partial<ServiceAssertionClaims>;
  try {
    header = JSON.parse(decodeBase64Url(headerPart));
    claims = JSON.parse(decodeBase64Url(bodyPart));
  } catch (error) {
    throw new ServiceAssertionError('malformed assertion');
  }
  if (JSON.stringify(header) !== JSON.stringify({ alg: 'HS256', typ: 'JWT' })) {
    throw new ServiceAssertionError('unsupported assertion header', 'assertion_header');
  }

  const expectedSignature = createHmac('sha256', secretFrom(options))
    .update(`${headerPart}.${bodyPart}`)
    .digest();
  const providedSignature = Buffer.from(signaturePart, 'base64url');
  if (expectedSignature.length !== providedSignature.length || !timingSafeEqual(expectedSignature, providedSignature)) {
    throw new ServiceAssertionError('invalid assertion signature', 'assertion_signature');
  }
  if (claims.iss !== ISSUER || claims.aud !== AUDIENCE) {
    throw new ServiceAssertionError('invalid assertion audience', 'assertion_audience');
  }
  if (expectedCourseId !== null && claims.course_id !== expectedCourseId) {
    throw new ServiceAssertionError('assertion course mismatch', 'assertion_course');
  }
  if (!Array.isArray(claims.scope) || requiredScopes.some((scope) => !claims.scope?.includes(scope))) {
    throw new ServiceAssertionError('assertion scope is insufficient', 'assertion_scope');
  }
  if (!claims.sub || !claims.jti || typeof claims.iat !== 'number' || typeof claims.exp !== 'number') {
    throw new ServiceAssertionError('assertion claims are incomplete', 'assertion_incomplete');
  }
  const maxTtl = options.maxTtlSeconds ?? MAX_ASSERTION_TTL_SECONDS;
  if (claims.exp - claims.iat > maxTtl) {
    throw new ServiceAssertionError('assertion lifetime exceeds the allowed maximum', 'assertion_lifetime');
  }
  if (claims.exp <= now) throw new ServiceAssertionError('assertion expired', 'assertion_expired');
  if (claims.iat > now) throw new ServiceAssertionError('assertion issued in the future', 'assertion_not_yet_valid');
  (options.replayStore ?? new InMemoryReplayStore()).consume({
    jti: claims.jti,
    issuer: claims.iss,
    audience: claims.aud,
    subject: claims.sub,
    courseId: claims.course_id,
    scopes: [...claims.scope],
    issuedAt: claims.iat,
    expiresAt: claims.exp,
    consumedAt: now,
  });
  return claims as ServiceAssertionClaims;
}

import { createHmac, timingSafeEqual } from 'node:crypto';

const ISSUER = 'campusmate-backend';
const AUDIENCE = 'openmaic-service';

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

export class ServiceAssertionError extends Error {}

export class InMemoryReplayStore {
  #used = new Map<string, number>();

  consume(jti: string, exp: number, now: number) {
    for (const [usedJti, expiresAt] of this.#used) {
      if (expiresAt <= now) this.#used.delete(usedJti);
    }
    if (this.#used.has(jti)) throw new ServiceAssertionError('assertion replay detected');
    this.#used.set(jti, exp);
  }
}

const defaultReplayStore = new InMemoryReplayStore();

function decodeBase64Url(value: string) {
  return Buffer.from(value, 'base64url').toString('utf8');
}

function secretFrom(options: VerifyOptions) {
  const secret = options.secret ?? process.env.OPENMAIC_INTERNAL_SECRET;
  if (!secret) throw new ServiceAssertionError('OPENMAIC_INTERNAL_SECRET is not configured');
  return secret;
}

export type VerifyOptions = {
  secret?: string;
  replayStore?: InMemoryReplayStore;
};

export function verifyServiceAssertion(
  token: string,
  expectedCourseId: string,
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
    throw new ServiceAssertionError('unsupported assertion header');
  }

  const expectedSignature = createHmac('sha256', secretFrom(options))
    .update(`${headerPart}.${bodyPart}`)
    .digest();
  const providedSignature = Buffer.from(signaturePart, 'base64url');
  if (expectedSignature.length !== providedSignature.length || !timingSafeEqual(expectedSignature, providedSignature)) {
    throw new ServiceAssertionError('invalid assertion signature');
  }
  if (claims.iss !== ISSUER || claims.aud !== AUDIENCE) throw new ServiceAssertionError('invalid assertion audience');
  if (claims.course_id !== expectedCourseId) throw new ServiceAssertionError('assertion course mismatch');
  if (!Array.isArray(claims.scope) || requiredScopes.some((scope) => !claims.scope?.includes(scope))) {
    throw new ServiceAssertionError('assertion scope is insufficient');
  }
  if (!claims.sub || !claims.jti || typeof claims.iat !== 'number' || typeof claims.exp !== 'number') {
    throw new ServiceAssertionError('assertion claims are incomplete');
  }
  if (claims.exp <= now) throw new ServiceAssertionError('assertion expired');
  if (claims.iat > now) throw new ServiceAssertionError('assertion issued in the future');
  (options.replayStore ?? defaultReplayStore).consume(claims.jti, claims.exp, now);
  return claims as ServiceAssertionClaims;
}

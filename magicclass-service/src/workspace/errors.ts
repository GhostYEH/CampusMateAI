/**
 * Workspace-layer failures.
 *
 * Each code maps to exactly one HTTP status at the route boundary, so the
 * gateway never has to guess and the browser never has to parse a message to
 * decide what to do. Messages are deliberately free of ids and paths — the
 * client already knows which workspace it asked for.
 */

export type WorkspaceErrorCode =
  | 'not_found'
  | 'revision_mismatch'
  | 'idempotency_conflict'
  | 'invalid_request'
  | 'document_rejected';

const STATUS: Record<WorkspaceErrorCode, number> = {
  not_found: 404,
  // 412 Precondition Failed is the correct answer for a failed If-Match; the
  // gateway maps it to 409 for the browser, which cannot act on the difference.
  revision_mismatch: 412,
  idempotency_conflict: 409,
  invalid_request: 400,
  document_rejected: 422,
};

export class WorkspaceError extends Error {
  readonly code: WorkspaceErrorCode;
  readonly status: number;
  readonly details: unknown;

  constructor(code: WorkspaceErrorCode, message?: string, details?: unknown) {
    super(message ?? code);
    this.name = 'WorkspaceError';
    this.code = code;
    this.status = STATUS[code];
    this.details = details;
  }
}

/** A missing row and a row that belongs to someone else are the same answer. */
export function notFound(): never {
  throw new WorkspaceError('not_found');
}

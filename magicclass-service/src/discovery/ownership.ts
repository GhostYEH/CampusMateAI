/**
 * Folder ownership lookup, kept in its own module so the workspace write path
 * can use it without importing the discovery repository (which in turn imports
 * the workspace repository for its paging helpers).
 *
 * The predicate lives here once. A workspace may only be filed into a folder
 * that is live and belongs to the same caller in the same course, and every
 * caller of this function treats "not owned" the same way it treats "does not
 * exist".
 */

import type { ServiceDatabase } from '../db/database.ts';

export function folderIsOwned(
  database: ServiceDatabase,
  input: { userId: string; courseId: string; folderId: string },
): boolean {
  const row = database.raw
    .prepare(
      `SELECT 1 AS present FROM folders
        WHERE id = ? AND user_id = ? AND course_id = ? AND deleted_at IS NULL`,
    )
    .get(input.folderId, input.userId, input.courseId);
  return Boolean(row);
}

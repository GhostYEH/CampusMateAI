# Worktree Consolidation and GitHub Publication Design

## Status

Approved for implementation on 2026-08-25.

## Context

The repository currently has several divergent development lines and a large
amount of uncommitted work spread across the primary working copy and
`.worktrees/`. The remote default branch is `origin/master` at `4d51aa14`.
The primary working copy is on `codex/android-secondary-navigation` at
`1d55e01b`, while the detached `edu-session-task5` worktree contains the child
commit `c81188cc`. The CPM worktree and the primary working copy also contain
different uncommitted Android counselor UI implementations.

File modification time is not a reliable definition of "latest" because the
same features were developed on divergent histories. Consolidation must use
commit ancestry, content comparison, tests, and feature intent.

## Goals

- Preserve every authored source change before removing any worktree.
- Produce one coherent project state containing the newest compatible work.
- Exclude local caches, build products, runtime uploads, and temporary QA
  captures from the published source tree.
- Verify the consolidated backend, Android, web, WeChat, ML, and Harmony code
  in proportion to the build tools available in the repository.
- Update `master` and push it to GitHub without force-pushing.
- Remove `.worktrees/` only after all retained work is represented by commits.

## Non-goals

- Reimplement or redesign product features unrelated to merge conflicts.
- Publish secrets, local `.env` files, generated packages, test caches, or
  screenshots used only for local visual verification.
- Rewrite public Git history or force-push the remote branch.
- Delete recovery branches or commits as part of filesystem cleanup.

## Decision

Use a preservation-first integration workflow. Create explicit recovery refs
for each dirty working copy, then consolidate on a `codex/` integration branch
based on the primary development line. Resolve overlapping changes
semantically, using tests and surrounding contracts instead of timestamps.
Merge the remote-backed `master` history into the integration line, verify the
result, then advance `master` to the verified merge and push normally through
the repository's configured proxy.

## Source Classification

### Primary working copy

Treat the primary working copy as the broadest and most recent development
baseline. Retain authored source, tests, configuration examples, and durable
design documentation. Review every untracked path before staging.

### `edu-session-task5`

Retain commit `c81188cc` and its three uncommitted follow-up changes. Where the
primary working copy already contains overlapping encrypted-session work,
combine the implementations rather than replacing whole files.

### `cpm-mobile-merge`

Retain its five modified and three untracked files. Reconcile the counselor
hero layout, digital-human stage, shell behavior, and tests against the newer
cross-platform work in the primary working copy.

### Clean and stale worktrees

Named branches already reachable from the selected development history do not
need content replay. For the two worktrees whose `.git` files still point to
`F:/demo1`, compare their files against `codex/edu-real-login` and
`codex/fix-edu-sync-result` before removal. Preserve any difference as a
recovery commit or archive before cleanup.

### Generated and local-only material

Do not publish `.codex` pytest caches, unsigned HAP output, generated build
trees, runtime community uploads, temporary GUI automation scripts, layout
dumps, or local QA screenshots unless a tracked project contract explicitly
requires a particular artifact. Add appropriate ignore rules when the current
rules do not cover recurring local output.

## Integration Sequence

1. Fetch remote refs through the configured `127.0.0.1:7897` proxy and verify
   that `origin/master` has not moved unexpectedly.
2. Create recovery branches/commits for the primary working copy,
   `cpm-mobile-merge`, and `edu-session-task5`; record the original tips.
3. Compare stale worktree contents with their surviving branch tips and save
   any unique files before removal.
4. Build a clean integration branch from the primary development line.
5. Integrate education-session persistence and CPM counselor UI changes in
   small, reviewable commits.
6. Merge `master` into the integration branch, resolving duplicate-history
   conflicts by retained behavior rather than wholesale side selection.
7. Run secret and artifact scans, targeted tests during conflict resolution,
   and the broad verification suite at the final tree.
8. Advance local `master` only after verification passes, then push
   `master:master` without force.
9. Remove registered worktrees with `git worktree remove`, prune stale Git
   metadata, delete confirmed residual directories, and verify `.worktrees/`
   is empty or absent.

## Conflict Policy

- Prefer additive reconciliation when two branches implement different parts
  of the same feature.
- Preserve current API contracts unless a newer test demonstrates an intended
  replacement.
- Keep tests from both sides and update them only when the consolidated
  behavior makes an old assertion invalid.
- Never select an entire directory with `ours` or `theirs` merely to finish a
  merge.
- Stop before publication if a conflict cannot be resolved from repository
  evidence without changing product intent.

## Verification

- Use the bundled JDK 21 at
  `android/.tools/jdk21-full/jdk-21.0.12+8` for every Java/Gradle command.
- Verify the JDK reports version `21.0.12` before Android builds.
- Run backend tests for all changed services and the broad backend suite.
- Run Android unit tests and an assemble task appropriate to the project.
- Run web and WeChat package tests/check scripts and production builds where
  defined by their package manifests.
- Run changed ML test suites and available Harmony tests/build checks.
- Run `git diff --check`, inspect the final staged changes, and scan for
  credentials and disallowed artifacts.
- Confirm the pushed `refs/heads/master` equals the verified local commit.

## Recovery and Cleanup

Every dirty worktree must have a named recovery ref before its directory is
removed. Worktree removal happens only after the final verified commit and
push. If Git refuses removal because unique files remain, inspect and preserve
them rather than using force. Stale directories are deleted only after their
resolved absolute paths are confirmed to be children of
`D:/File/demo1/.worktrees`.

## Alternatives Considered

### Replace `master` with the primary working copy

Rejected because it would require history rewriting or discard the divergent
CPM integration already present on the remote branch.

### Publish an integration branch and keep all worktrees

Safer for review, but rejected as the final workflow because the user
explicitly requested cleanup and publication to the main GitHub repository.
Recovery refs provide rollback without retaining multi-gigabyte directories.

## Success Criteria

- All retained authored changes exist in Git commits.
- The consolidated tree passes the agreed verification commands.
- GitHub `master` points to the verified consolidated commit via a normal push.
- No force-push occurs.
- `.worktrees/` is removed or contains no worktree data.
- Recovery refs and a concise merge record identify the pre-cleanup states.

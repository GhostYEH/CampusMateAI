# Curated Learned Lessons

This file is for stable, reviewed lessons promoted from the local WeChat Mini Program experience ledger. Keep entries short, reusable, and free of secrets or private user data.

## Current Baseline

- Run `npm run wx:learn -- "<task>"` before nontrivial WeChat Mini Program work.
- Record unresolved domain failures with `npm run wx:experience -- record ...`.
- Resolve records with `--root-cause`, `--fix`, and `--rule` once the fix is verified.
- Use the global `error-ledger` for broad tool failures and this ledger for WeChat-specific lessons.
- Keep project-specific records under `--scope project`; promote reusable lessons with `--scope global` only after the fix is verified.
- Add atomic labels with `--task-type`, `--stage`, `--area`, `--capability`, `--framework`, `--experience`, and `--severity` so preflight can retrieve the lesson precisely.
- Automatic audit runs after `wx:experience record/resolve/dedupe` and `wx:validate`; run `npm run wx:experience-audit` manually only for explicit maintenance passes. Use the report to resolve stale records, dedupe repeats, promote stable cross-project lessons, and turn high-frequency fixes into templates/checklists.

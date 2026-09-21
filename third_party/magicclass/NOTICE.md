# magic class provenance notice

This directory records the audited source boundary for magic class `v1.0.3`.

- Repository: `https://github.com/THU-MAIC/OpenMAIC.git`
- Tag: `v1.0.3`
- Commit: `e693e11a81644f84c258df73dbda378643520a62`
- License: MIT; see `LICENSE`.
- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.

## Local deviation: the magic class brand patch

The tree under `magicclass-app/` is the commit above with exactly **one** additional,
replayable transformation: `scripts/magicclass-brand.mjs`, which renames the user-visible
brand `OpenMAIC` to `magic class` and the npm identity `openmaic` / `@openmaic/*` to
`magicclass` / `@magicclass/*`.

`source-manifest.sha256` still pins **upstream** bytes. To prove that nothing else changed,
the patch is inverted and every file is re-hashed:

```bash
node scripts/magicclass-brand.mjs verify
```

A pass means `magicclass-app/` = this upstream commit + the rules in that one file. Anything
beyond those rules shows up as a mismatch. Upstream MIT license and copyright stay in place
(`magicclass-app/LICENSE`).

Two carve-outs are deliberate, not oversights:

- `magicclass-app/render-service/` (the app's own render service — not the repo-root
  `render-service/`) keeps its two **published** `@openmaic/dsl` / `@openmaic/renderer`
  dependencies verbatim. Those are third-party packages on npm, not our workspace packages;
  renaming them to `@magicclass/*` produces an install that cannot resolve (verified: both
  names 404 on the npm registry). `magicclass-brand.mjs` therefore skips that subtree.
- `magicclass-app/packages/@magicclass/*` **are** our workspace packages, so those do get
  renamed from `@openmaic/*`.

# magic class provenance notice

This directory records the audited source boundary for magic class `v1.0.3`.

- Repository: `https://github.com/THU-MAIC/OpenMAIC.git`
- Tag: `v1.0.3`
- Commit: `e693e11a81644f84c258df73dbda378643520a62`
- License: MIT; see `LICENSE`.
- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.

## Local deviations: branding and replayable features

The tree under `magicclass-app/` starts from the commit above. The branding rules in
`scripts/magicclass-brand.mjs` rename the user-visible
brand `OpenMAIC` to `magic class` and the npm identity `openmaic` / `@openmaic/*` to
`magicclass` / `@magicclass/*`.

Functional changes are recorded separately in `scripts/magicclass-feature.edits.json`:
exact reversible replacements for upstream files and complete contents for added files.
Other known deviations are individually explained in `DECLARED_DEVIATIONS` in the audit
script. Changes must be recorded in the appropriate patch layer before they can pass.

`source-manifest.sha256` still pins **upstream** bytes. The feature and brand patches are
inverted before every upstream file is re-hashed; added files are checked against their
recorded contents:

```bash
node scripts/magicclass-brand.mjs check
node scripts/magicclass-brand.mjs verify
```

A pass means `magicclass-app/` = this upstream commit + brand rules + recorded features +
explicitly declared deviations. Unrecorded edits or added files fail the check. The source
integrity CI gate runs both commands and the patch tests. Upstream MIT license and copyright stay in place
(`magicclass-app/LICENSE`).

Two carve-outs are deliberate, not oversights:

- `magicclass-app/render-service/` (the app's own render service — not the repo-root
  `render-service/`) keeps its two **published** `@openmaic/dsl` / `@openmaic/renderer`
  dependencies verbatim. Those are third-party packages on npm, not our workspace packages;
  renaming them to `@magicclass/*` produces an install that cannot resolve (verified: both
  names 404 on the npm registry). `magicclass-brand.mjs` therefore skips that subtree.
- `magicclass-app/packages/@magicclass/*` **are** our workspace packages, so those do get
  renamed from `@openmaic/*`.

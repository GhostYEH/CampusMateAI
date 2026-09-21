# magic class provenance notice

This directory records the audited source boundary for magic class `v1.0.3`.

- Repository: `https://github.com/THU-MAIC/magicclass.git`
- Tag: `v1.0.3`
- Commit: `e693e11a81644f84c258df73dbda378643520a62`
- License: MIT; see `LICENSE`.
- The source checkout itself, package managers, build output, runtime data, logs, credentials and local configuration are not vendored here.

## Local deviation: the magic class brand patch

The tree under `magicclass-app/` is the commit above with exactly **one** additional,
replayable transformation: `scripts/magicclass-brand.mjs`, which renames the user-visible
brand to `magic class` and the npm identity `magicclass` / `@magicclass/*` to
`magicclass` / `@magicclass/*`.

`source-manifest.sha256` still pins **upstream** bytes. To prove that nothing else changed,
the patch is inverted and every file is re-hashed:

```bash
node scripts/magicclass-brand.mjs verify
```

A pass means `magicclass-app/` = this upstream commit + the rules in that one file. Anything
beyond those rules shows up as a mismatch. Upstream MIT license and copyright stay in place
(`magicclass-app/LICENSE`); `render-service/` keeps its two published `@magicclass/*`
dependencies because those are third-party packages on npm, not our workspace packages.

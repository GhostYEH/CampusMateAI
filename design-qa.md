# Campus News Hub Design QA

- source visual truth path: `C:\Users\32883\AppData\Local\Temp\codex-clipboard-cdd4f785-03fa-4e47-a3c0-13270a6ad128.png`
- implementation screenshot paths:
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\news-main.png`
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\news-bottom.png`
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\news-no-result.png`
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\news-360dp-list.png`
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\news-font130-target2.png`
- comparison evidence:
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\campus-news-comparison.png`
  - `F:\demo1\.worktrees\campus-news-hub\artifacts\campus-news-focused-comparison.png`
- viewport: Pixel 10 Pro emulator at 426.7dp wide (1280x2856, 480dpi), plus 360x800dp override (1080x2400, 480dpi)
- state: populated/latest, scrolled-to-bottom, search focus with IME, no-result search, and 130% system font scale

## Full-view comparison evidence

The homepage reference and rendered secondary page were placed in one combined image before review. The reference only specifies the homepage campus-news module, not a complete secondary-page composition, so the comparison treats its palette, surface treatment, typography hierarchy, radius, and density as the visual source of truth rather than asserting pixel-for-pixel page parity.

The secondary page preserves the app's light gray canvas, white rounded surfaces, blue-violet emphasis, dark title hierarchy, muted metadata, and restrained single-pixel borders. The page header, search field, filters, result count, and news cards form a clear top-to-bottom scan path without overlap at either tested width.

## Focused region comparison evidence

The homepage campus-news card and the first secondary-page news card were placed together in a focused comparison. The secondary card deliberately omits the homepage thumbnail because the list page prioritizes filtering and scan density, but it preserves the same headline/summary hierarchy, rounded white surface, cool gray outline, and blue semantic accent. Icons use the existing Material icon family; no placeholder imagery, emoji, custom SVG, or CSS-like drawn substitute is present.

## Findings

No actionable P0, P1, or P2 findings remain.

- Typography: Chinese system typography remains readable at default and 130% font scale. Titles, summaries, metadata, chip labels, and empty-state copy do not overlap or truncate unexpectedly in the campus-news screen.
- Spacing and layout rhythm: 16dp page gutters, consistent 12-16dp vertical gaps, 18dp search radius, and rounded cards align with the existing product language. The horizontal category row scrolls on 360dp rather than compressing labels.
- Colors and tokens: background, surface, line, primary, primary-soft, muted, and text-primary values are sourced from the app theme and visually match the reference's cool neutral and blue-violet direction.
- Image quality and asset fidelity: the source card imagery remains on the homepage. The secondary page does not introduce replacement imagery, so there is no crop, scaling, compression, masking, or asset-substitution defect.
- Copy and content: search guidance, category names, read state, sorting, source/time metadata, and no-result messaging are coherent and fit their containers.
- Interaction and accessibility: search with the IME open remains usable; all controls retain practical touch targets; the no-result state centers correctly; the last card scrolls fully above the floating dock and system navigation inset.

## Open Questions

- The supplied reference does not define loading, refresh-error, or secondary-page detail visuals. These states follow the app's existing shared components and were code/build verified, but only the populated and no-result states were visually captured in this QA pass.
- At 130% font scale on a 360dp viewport, the pre-existing global dock label `AI 校园助手` becomes visually tight. It does not overlap the campus-news content or block navigation and is outside the new screen component.

## Patches made since the previous QA pass

- No layout patch was required. The implemented screen passed the rendered checks as built.

## Implementation checklist

- [x] Verify status-bar clearance and header alignment.
- [x] Verify search, category row, sort/read controls, and populated cards at 426.7dp.
- [x] Verify 360dp horizontal resilience.
- [x] Verify 130% text scaling on the campus-news screen.
- [x] Verify IME and no-result layout.
- [x] Verify final content scrolls above the floating bottom dock and navigation inset.
- [x] Compare source and implementation in combined full-view and focused images.

## Follow-up polish

- Optional P3: shorten or responsively size the existing global dock's longest label for extra comfort at large system font scales.

final result: passed

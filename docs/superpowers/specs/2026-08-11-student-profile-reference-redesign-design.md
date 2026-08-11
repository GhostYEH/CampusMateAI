# Student Profile Reference Redesign

## Goal

Rebuild the existing student personal center so its desktop composition closely matches the supplied reference image while preserving all current data sources, routes, and interactions.

## Visual Direction

- Light blue-white campus workspace with a narrow navigation rail and compact top command bar.
- Dense but calm information hierarchy: profile identity banner first, three tabs second, then a two-column dashboard.
- Soft 14-16 px corners, thin blue-gray borders, subtle cool-tinted shadows, and restrained blue-violet accents.
- Existing Noto Sans SC typography and Phosphor icons remain the only type and icon systems.
- The existing campus illustration is reused as the banner decoration. No new placeholder art is introduced.

## Page Structure

1. Keep the existing application shell, route, global search, notification access, and account navigation.
2. Profile heading contains the `PROFILE / 个人中心` kicker, page title, and explanatory copy.
3. Profile banner contains the avatar, identity metadata, account state, four live statistic cards, and decorative campus art.
4. Tabs remain `资料编辑`, `我的工具`, and `设置`.
5. Overview tab uses the reference layout:
   - Left: basic profile information.
   - Right top: campus identity card.
   - Left bottom: six compact quick-entry tiles.
   - Right bottom: recent study activity timeline.
6. Tools and settings tabs retain their existing functionality and adopt the same visual tokens.

## Data And Interaction Preservation

- Continue loading profile, dashboard, and study-session data from the current student API services.
- Keep profile edit and save behavior, copy-student-number feedback, tab switching, quick-route navigation, refresh, and preference toggles.
- Keep loading, empty, success, and error states.
- Do not add new routes or change API payloads.

## Responsive Behavior

- Match the 1680 x 940 desktop reference first.
- Collapse the banner statistics below identity content on medium widths.
- Collapse the overview dashboard to one column on tablets.
- Use two-column statistic and quick-entry grids on narrow mobile screens, then one column for quick entries at the smallest breakpoint.
- Keep keyboard focus states, readable contrast, and reduced-motion behavior.

## Acceptance Criteria

- At the reference viewport, the shell proportions, banner height, card grid, typography hierarchy, spacing, radii, and palette visibly match the supplied image.
- All existing profile interactions remain operational.
- The production build passes.
- A same-viewport browser screenshot is compared with the source and `design-qa.md` ends with `final result: passed`.

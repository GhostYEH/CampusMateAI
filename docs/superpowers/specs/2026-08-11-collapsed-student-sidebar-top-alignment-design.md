# Collapsed Student Sidebar Top Alignment Design

## Goal

Align the student sidebar brand mark and profile avatar on the same visual axis in desktop collapsed mode, while preserving the existing navigation, expanded layout, mobile drawer, colors, icon library, and route behavior.

## Root Cause

The collapsed sidebar is 82 px wide with 17 px horizontal sidebar padding, leaving a 48 px content rail. Two expanded-state layouts continue to participate after their text is hidden:

- The brand retains 12 px horizontal padding, so its 47 px mark starts from the padded content edge and overflows to the right.
- The profile button retains a three-column grid (`49px minmax(0, 1fr) 16px`). Hiding the profile copy and caret does not remove those explicit tracks, so centering the oversized grid pushes the avatar to the left.

The existing regression test checks lower-specificity generic rules (`.sidebar .brand-mark` and `.sidebar .avatar`). Student-specific rules loaded later still determine the final 47 px and 49 px sizes, so that test passes without covering the visible layout.

## Selected Design

Create a desktop collapsed-state contract scoped to `.student-layout.collapsed`:

- Treat the sidebar's 48 px inner width as the shared control rail.
- Remove horizontal padding from the brand and center a 46 px brand mark.
- Replace the profile button's three-column grid with a single centered track, remove horizontal padding, and use a 44 px avatar.
- Keep the full profile button as the click target and retain its existing soft background and radius.
- Preserve current vertical grouping, navigation order, active state, hover behavior, icons, and all Vue event handlers.
- Apply the compact alignment only above the existing 900 px mobile breakpoint so the mobile drawer remains an expanded navigation surface.

## Alternatives Considered

1. Only reset the brand padding and profile grid while keeping the 47 px and 49 px assets. This fixes the offset but leaves the two top elements visually heavier than the 48 px navigation rail.
2. Extract a reusable sidebar rail-item component and refactor the shell. This could improve long-term consistency, but it adds template and interaction risk beyond the requested visual repair.

The selected CSS-only contract is the smallest change that fixes the root cause and produces a consistent collapsed rail.

## Implementation Boundaries

- Modify only the focused student sidebar CSS and its regression test.
- Do not change `AppShell.vue`, navigation data, routes, icon assets, or unrelated sidebar active-indicator work.
- Do not modify the user's other uncommitted Web, Android, backend, HarmonyOS, or generated `dist` changes.

## Verification

1. Replace the current generic-selector regression with assertions against the final student collapsed selectors.
2. Run the test before implementation and confirm it fails because the collapsed alignment contract is absent.
3. Add the minimal scoped CSS and confirm the focused test passes.
4. Run the complete Web Node test suite and the Vite production build.
5. Compare the collapsed sidebar at the same narrow viewport: brand mark, avatar, navigation icons, and bottom actions must share one center line; expanded and mobile states must remain unchanged.

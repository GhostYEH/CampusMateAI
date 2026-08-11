# Student Profile Reference Redesign Plan

1. Audit the current profile view, app shell, shared design tokens, and existing asset inventory.
2. Restructure the profile template only where the reference layout requires it, keeping API and router behavior unchanged.
3. Add profile-scoped shell and content styles for the reference desktop viewport and responsive fallbacks.
4. Build the Vue application and resolve markup, style, and accessibility regressions.
5. Run the local app, capture the profile route at 1680 x 940, and compare it with the supplied source image.
6. Fix all P0, P1, and P2 visual mismatches, verify interactions, and append the final profile result to `design-qa.md`.

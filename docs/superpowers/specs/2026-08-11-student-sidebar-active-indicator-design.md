# Student Sidebar Active Indicator Design

## Goal

Refine the student web sidebar's selected navigation state so its left accent reads as a clean indicator instead of bending around the button's rounded corners.

## Scope

- Keep the existing light-purple selected background, icon, label, spacing, radius, and routing behavior.
- Replace the active button's inset left shadow with a separate, vertically centered accent bar.
- Apply the treatment only to active primary navigation buttons in the student sidebar.
- Preserve collapsed and mobile sidebar behavior.

## Visual Specification

- The active button remains `#eef0ff` with foreground color `#4655df`.
- The indicator uses the existing accent color `#5665f4`.
- The indicator is 3 px wide, 24 px tall, vertically centered, and has fully rounded ends.
- The button becomes the positioning context for the indicator.
- The indicator does not intercept pointer events.

## Interaction And Accessibility

- No navigation behavior changes.
- Hover styling remains unchanged.
- Active-state meaning continues to be conveyed by background and foreground color in addition to the indicator.
- Reduced-motion behavior is unaffected because the indicator is static.

## Verification

- Build the Vue application successfully.
- Confirm the generated active-state CSS no longer contains the inset shadow.
- Visually verify expanded, collapsed, and narrow sidebar states when a browser preview is available.

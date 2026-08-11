# Sticky Secondary Navigation Design

## Goal

Make every secondary Android destination reliably navigable while its content scrolls: its top navigation remains visible and every applicable destination has a consistent back action.

## Scope

- Add shared Compose navigation chrome for secondary destinations.
- The chrome contains a persistent title and a left-aligned circular back button.
- The button uses a translucent, frosted-glass approximation: a semi-transparent surface, subtle light border and highlight, and accessible opaque fallback.
- Apply the chrome centrally from the navigation host for non-root destinations without changing route names, arguments, business actions, or the bottom dock.
- Keep screen-specific hero headers as scrollable content where they are part of the visual design.

## Interaction and Layout

- The fixed bar is outside each destination's LazyColumn or verticalScroll container.
- The back target calls the existing NavController.popBackStack callback.
- Root destinations retain bottom navigation and do not receive secondary chrome.
- Existing fixed top bars migrate to the shared chrome to avoid duplicate back controls.
- Content receives top inset spacing so the chrome cannot obscure tappable content.

## Visual System

- 44 dp circular tap target with an ArrowBack icon and Chinese accessibility label 返回.
- Light mode uses a translucent existing surface token, white highlight border, and soft indigo shadow.
- Dark mode keeps icon and border contrast. No new brand colors or dependencies.
- The app's reduce-motion preference adds no decorative navigation motion.

## Validation

- Unit-test route classification: root routes omit chrome; secondary route patterns expose a nonblank title.
- Compile the Android debug variant and run all unit tests.
- Manually check Settings, Campus News detail, and Learning Tong login: the button remains visible and tappable while scrolling and does not cover content.

## Constraints

- Preserve existing uncommitted notification and Learning Tong changes.
- Do not rename routes, change primary navigation labels, or alter business behavior.


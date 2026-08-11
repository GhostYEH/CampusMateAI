# Android Lost & Found Reference Redesign

## Goal

Rebuild the Android lost-and-found browse screen so its default state closely matches the supplied mobile reference while retaining the app's current repository-backed data, navigation, publishing, and filtering behavior.

## Scope

- Target: `LostFoundScreen` only, reached through the existing `lostfound` route.
- Preserve: item repository loading, lost/found tab filtering, text search, category filtering, location selector, sort order, item-detail navigation, publishing navigation, and "My posts" navigation.
- Do not modify the existing detail, publishing, or "My posts" screens beyond their existing navigation entry points.
- Do not touch the unrelated uncommitted notification or web changes in the workspace.

## Visual Reference Contract

The provided screenshot is the source of truth for the default lost-items state.

1. Use a light periwinkle-to-white hero region with the existing `hero_lost_found` illustration positioned on the right.
2. Place the back button at upper left, a rounded "我的发布" button and circular plus button at upper right, and the title/subtitle on the left. Match the reference's generous vertical breathing room.
3. Render the lost/found switch as one wide, white rounded container with a vivid indigo selected half and matching leading icons.
4. Keep the search input, category chips, location selector, and sort selector in the same top-to-bottom order, using white surfaces, cool gray borders, circular or softly rounded geometry, and blue selected states.
5. Render result items as tall, white rounded cards with a large left thumbnail, title and orange status tag at right, colored type/category chips, location/time row, and one-line description.
6. Continue using the app shell's existing bottom navigation; content must reserve its dock height so the final card is never obscured.

## Layout and Styling

- Use Compose dimensions that scale from the existing phone layout rather than fixed pixel coordinates.
- Screen background: near-white with a restrained cool-blue tint.
- Primary color: the existing indigo theme primary; selected controls use this color, with white labels/icons.
- Card/background surface: white; border: very pale blue-gray; shadow/elevation: subtle and limited to hero/card separation.
- Corners: hero/action buttons circular or capsule-shaped; controls around 18-24 dp; listing cards around 26-30 dp.
- Typography: strong dark-navy display title; bold card titles; readable muted metadata. Use the app's existing theme colors/type system whenever it does not conflict with the reference.
- Assets: reuse `hero_lost_found.png`, `lost_power_bank.png`, `lost_book.png`, `lost_card.png`, and `lost_earbuds.png`. Use Material icon assets already in the app for controls rather than drawing replacement graphics.

## Interaction and State

- Lost/found switch updates the repository filter and selected visual state.
- Search text filters items by the existing repository logic.
- Category chips update the selected category; the chip row must stay usable on narrow displays (horizontal scrolling if necessary).
- Location opens the existing populated dropdown and applies its selection.
- Sort toggles newest-first/oldest-first and updates the label.
- Tapping a result opens its existing detail route. Back, publish, and "我的发布" use their current callbacks.
- Empty results retain a calm, readable empty state below the controls.

## Validation

1. Compile the Android debug variant and run relevant unit tests.
2. Render/run the lost-and-found screen at a phone viewport matching the supplied reference.
3. Compare the reference and rendered screen side by side for hero composition, spacing, control geometry, colors, typography, card proportions, and bottom-dock clearance.
4. Exercise all first-screen controls: tab, search, every category, location dropdown, sort, item card, publish, and "我的发布".

## Acceptance Criteria

- The initial lost-items screen has the same information hierarchy and recognizably the same visual treatment as the reference.
- Existing data and all specified interactions continue to work.
- The screen compiles without new warnings or errors and leaves unrelated workspace changes untouched.

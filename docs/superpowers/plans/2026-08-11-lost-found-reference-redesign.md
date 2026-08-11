# Lost & Found Reference Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Android lost-and-found browse screen to faithfully match the supplied reference while preserving every existing first-screen interaction.

**Architecture:** Keep `LostFoundRepository` as the single data source and retain the existing navigation callbacks. Extract the small browse-filter state and its repository filter arguments into a pure Kotlin type so functional state transitions remain unit-testable; keep all visual composition in `LostFoundScreen.kt`.

**Tech Stack:** Kotlin, Jetpack Compose Material 3, AndroidX Compose UI testing dependencies already declared by the app, JUnit 4, Gradle.

## Global Constraints

- Target only the `lostfound` browse route; existing detail, publish, and my-posts routes remain intact.
- The supplied screenshot is the source of truth for the default lost-items state.
- Reuse `hero_lost_found.png`, `lost_power_bank.png`, `lost_book.png`, `lost_card.png`, and `lost_earbuds.png`; do not create placeholder artwork.
- Preserve repository-backed loading, lost/found filter, search, category filtering, location selection, sort selection, card navigation, publishing navigation, and my-posts navigation.
- Leave all unrelated existing working-tree changes untouched.

---

## File Structure

- Create: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseState.kt` — immutable screen filter state and conversion to repository arguments.
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseStateTest.kt` — JVM tests for tab, category, location, and sorting state.
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundScreen.kt` — reference-faithful Compose layout and bindings to the extracted state.
- Modify: `docs/superpowers/plans/2026-08-11-lost-found-reference-redesign.md` — mark each completed step while executing; do not change product requirements.

### Task 1: Extract and test browse filter state

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseState.kt`
- Create: `android/app/src/test/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseStateTest.kt`

**Interfaces:**
- Consumes: `LostFoundKind` from `data/model/LostFoundItem.kt` and category/location labels shown by the Compose screen.
- Produces: `LostFoundBrowseState(kind: LostFoundKind, keyword: String, category: String, location: String, newestFirst: Boolean)` and `repositoryLocation(): String` for `LocalLostFoundRepository.filter`.

- [ ] **Step 1: Write failing state tests**

```kotlin
class LostFoundBrowseStateTest {
    @Test fun `found tab exposes found kind`() {
        assertEquals(LostFoundKind.FOUND, LostFoundBrowseState(kind = LostFoundKind.FOUND).kind)
    }

    @Test fun `all locations normalize to repository all value`() {
        assertEquals("全部", LostFoundBrowseState(location = "全部地点").repositoryLocation())
    }

    @Test fun `selected filters retain the entered values`() {
        val state = LostFoundBrowseState(
            keyword = "充电宝", category = "电子产品", location = "图书馆三楼", newestFirst = false,
        )
        assertEquals("充电宝", state.keyword)
        assertEquals("电子产品", state.category)
        assertEquals("图书馆三楼", state.repositoryLocation())
        assertFalse(state.newestFirst)
    }
}
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `cd android; .\\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.ui.screens.lostfound.LostFoundBrowseStateTest`

Expected: FAIL because `LostFoundBrowseState` does not exist.

- [ ] **Step 3: Implement the minimal immutable state type**

```kotlin
data class LostFoundBrowseState(
    val kind: LostFoundKind = LostFoundKind.LOST,
    val keyword: String = "",
    val category: String = "全部",
    val location: String = "全部地点",
    val newestFirst: Boolean = true,
) {
    fun repositoryLocation(): String = if (location == "全部地点") "全部" else location
}
```

Keep labels in one place so the screen uses the same defaults as the repository filter.

- [ ] **Step 4: Run state and repository tests**

Run: `cd android; .\\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.ui.screens.lostfound.LostFoundBrowseStateTest --tests com.example.campusai.LocalLostFoundRepositoryTest`

Expected: PASS; the new state tests and existing filter/persistence tests are green.

- [ ] **Step 5: Commit the focused state change**

```powershell
git add -- android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseState.kt android/app/src/test/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseStateTest.kt
git commit -m "feat: add lost and found browse state"
```

### Task 2: Recompose the browse screen to match the reference

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundScreen.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseState.kt`

**Interfaces:**
- Consumes: `LostFoundBrowseState.repositoryLocation()` and existing `LostFoundRepository.items` flow.
- Produces: the `LostFoundScreen(repository, onBack, onOpenDetail, onOpenPublish, onOpenMine)` route function with unchanged callback signature.

- [ ] **Step 1: Wire the screen to the tested state**

Replace five independent remembered filter fields with one state value:

```kotlin
var browseState by remember { mutableStateOf(LostFoundBrowseState()) }
val filtered = remember(items, browseState) {
    LocalLostFoundRepository.filter(
        items = items,
        kind = browseState.kind,
        keyword = browseState.keyword,
        category = browseState.category,
        location = browseState.repositoryLocation(),
        newestFirst = browseState.newestFirst,
    )
}
```

Each control updates only its relevant property with `browseState = browseState.copy(...)`; do not alter repository or route code.

- [ ] **Step 2: Implement the measured reference layout**

Rebuild the private composables in `LostFoundScreen.kt` with this hierarchy:

```text
LazyColumn (cool near-white background, horizontal 16 dp, dock-safe bottom padding)
  Hero (periwinkle gradient + right illustration + left title/subtitle + top controls)
  Mode switch (white capsule, indigo selected segment, bag/campaign icons)
  Search capsule
  Horizontally-scrollable category chips
  Location and sort controls
  Result cards (large 100-112 dp thumbnail, metadata and status chip)
```

Use `Brush.linearGradient` for the hero background, `painterResource(R.drawable.hero_lost_found)` for the supplied hero, Material icons for back/add/search/location/sort and the two mode icons, and `BottomDockReservedHeight + 18.dp` as the lazy-list bottom padding. Preserve `LostImage` URI loading and the existing seeded resource mapping.

- [ ] **Step 3: Preserve every interaction in the new visual components**

Bind and verify these exact actions:

```kotlin
LostTabs(selectedKind = browseState.kind) { browseState = browseState.copy(kind = it) }
SearchBox(value = browseState.keyword) { browseState = browseState.copy(keyword = it) }
CategoryRow(selected = browseState.category) { browseState = browseState.copy(category = it) }
LostDropdown(selected = browseState.location) { browseState = browseState.copy(location = it) }
SortButton(newest = browseState.newestFirst) { browseState = browseState.copy(newestFirst = !browseState.newestFirst) }
```

Keep `onBack`, `onOpenDetail(item.id)`, `onOpenPublish`, and `onOpenMine` unchanged. Ensure the category row can scroll horizontally when all six labels cannot fit rather than shrinking text below readable size.

- [ ] **Step 4: Compile the app before visual QA**

Run: `cd android; .\\gradlew.bat :app:assembleDebug`

Expected: `BUILD SUCCESSFUL` and a debug APK under `android/app/build/outputs/apk/debug/`.

- [ ] **Step 5: Commit only the screen implementation**

```powershell
git add -- android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundScreen.kt android/app/src/main/java/com/example/campusai/ui/screens/lostfound/LostFoundBrowseState.kt
git commit -m "feat: redesign lost and found browse screen"
```

### Task 3: Run functional and visual acceptance checks

**Files:**
- Modify: `docs/superpowers/plans/2026-08-11-lost-found-reference-redesign.md`

**Interfaces:**
- Consumes: the compiled debug app and the supplied reference image.
- Produces: recorded verification evidence and a completed plan checklist.

- [ ] **Step 1: Run the relevant JVM test suite**

Run: `cd android; .\\gradlew.bat :app:testDebugUnitTest`

Expected: `BUILD SUCCESSFUL`, including `LostFoundBrowseStateTest` and `LocalLostFoundRepositoryTest`.

- [ ] **Step 2: Validate all first-screen interactions on a device or emulator**

Open `lostfound` and verify in this order: open back navigation, tap \"我的发布\", open publish via plus, change to 招领, return to 失物, search for \"充电宝\", select \"电子产品\", open/select a location, toggle sort, and open a result card. Reset filters and confirm the default list returns.

Expected: every action reaches its existing route or updates the visible repository-backed list without crash or layout overlap.

- [ ] **Step 3: Perform side-by-side visual QA**

Capture the default lost-items screen at the same phone portrait viewport as the reference. Put the capture and `C:/Users/32883/AppData/Local/Temp/codex-clipboard-0f4549b0-ab56-4bbe-b679-fd0209ccdfed.png` into one comparison image, then inspect: hero position and height, title/action placement, selected-tab fill, search/filter dimensions, chip row wrapping/scrolling, card proportions, thumbnail crop, typography, and bottom dock clearance. Correct any visible mismatch in `LostFoundScreen.kt` and repeat the comparison once.

Expected: no clipped controls or cards; the initial information hierarchy, spacing, colors, and geometry visibly match the reference.

- [ ] **Step 4: Record completion and commit the checklist**

Mark the completed checkboxes in this plan, then run:

```powershell
git add -- docs/superpowers/plans/2026-08-11-lost-found-reference-redesign.md
git commit -m "docs: record lost and found redesign verification"
```

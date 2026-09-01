# Android Focus Scenes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Android focus session open as an immersive original scene with persistent ambient sound, adaptive liquid-glass controls, and an uninterrupted CampusMate robot animation.

**Architecture:** A small `data/focus/scene` package owns scene metadata, preference normalization, playback policy, and the Media3 audio controller. A focused Compose file owns the generated backdrop, scene picker, ambient controls, and glass panels; `FocusAssistantScreen.kt` keeps all existing session, robot, voice, and observation state and composes the new experience around it. `CampusGlassScene` gains an optional custom background while preserving every existing call site.

**Tech Stack:** Kotlin, Jetpack Compose, Media3 ExoPlayer, Android SharedPreferences, bundled Backdrop liquid glass, JUnit 4, Image Gen, ffmpeg-generated WebP/Ogg assets.

**Spec:** `docs/superpowers/specs/2026-09-01-android-focus-scenes-design.md`

## Global Constraints

- Android/JVM commands must use `android/.tools/jdk21-full/jdk-21.0.12+8`; stop if it is absent.
- Work directly on `master`; do not modify backend APIs, database schemas, Harmony, Web, or WeChat clients.
- Keep `FocusSpaceGuide` continuously composed while the selected scene changes; do not wrap the robot in `key(scene)` or a scene-keyed `AnimatedContent`.
- Environment sound defaults to off, persists locally, and never prevents a focus session from running.
- Generate original images and procedural audio; do not copy assets from `F:/File/summer-checkin-master`.
- Reuse the existing adaptive liquid-glass implementation and its API-level/reduce-motion fallbacks.

---

### Task 1: Scene domain, preferences, and playback policy

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/data/focus/scene/FocusScene.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/focus/scene/FocusScenePreferences.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/focus/scene/FocusAmbientPolicy.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/focus/scene/FocusScenePreferencesTest.kt`
- Test: `android/app/src/test/java/com/example/campusai/data/focus/scene/FocusAmbientPolicyTest.kt`

**Interfaces:**
- Produces: `enum class FocusScene`, `data class FocusSceneSettings`, `class FocusScenePreferenceStore`, and `FocusAmbientPolicy.targetVolume(...)`.
- Consumes: `FocusVoicePhase` from the existing voice subsystem.

- [ ] **Step 1: Write failing scene settings tests**

```kotlin
class FocusScenePreferencesTest {
    @Test fun defaultsToRainyRoomWithSoundOff() {
        assertEquals(FocusScene.RAINY_ROOM, FocusScene.fromStoredId(null))
        assertFalse(FocusSceneSettings.DEFAULT.ambientEnabled)
        assertEquals(.32f, FocusSceneSettings.DEFAULT.volume)
    }

    @Test fun unknownSceneAndInvalidVolumeAreNormalized() {
        val value = FocusSceneSettings.normalized("missing", true, 4.2f)
        assertEquals(FocusScene.RAINY_ROOM, value.scene)
        assertEquals(1f, value.volume)
    }
}
```

- [ ] **Step 2: Run the settings test and confirm it fails**

Run from `android/`: `./gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.data.focus.scene.FocusScenePreferencesTest"`

Expected: FAIL because the scene classes do not exist.

- [ ] **Step 3: Implement scene metadata and preference normalization**

```kotlin
enum class FocusScene(val storedId: String, val title: String, val subtitle: String) {
    RAINY_ROOM("rainy_room", "雨夜自习室", "让雨声替你隔开喧闹"),
    QUIET_LIBRARY("quiet_library", "静谧图书馆", "在翻页声里稳稳向前"),
    FOREST_MORNING("forest_morning", "林间晨读", "跟着清晨的风慢慢进入状态");

    companion object {
        fun fromStoredId(value: String?): FocusScene = entries.firstOrNull { it.storedId == value } ?: RAINY_ROOM
    }
}

data class FocusSceneSettings(
    val scene: FocusScene,
    val ambientEnabled: Boolean,
    val volume: Float,
) {
    companion object {
        val DEFAULT = FocusSceneSettings(FocusScene.RAINY_ROOM, false, .32f)
        fun normalized(sceneId: String?, enabled: Boolean, volume: Float) =
            FocusSceneSettings(FocusScene.fromStoredId(sceneId), enabled, volume.coerceIn(0f, 1f))
    }
}
```

`FocusScenePreferenceStore` must use an application-context `SharedPreferences` file named `focus_scene_preferences`, load through `FocusSceneSettings.normalized`, and save `scene.storedId`, `ambientEnabled`, and `volume` atomically with `edit()`.

- [ ] **Step 4: Write failing ambient policy tests**

```kotlin
class FocusAmbientPolicyTest {
    @Test fun soundRequiresOptInRunningSessionAndForegroundPage() {
        val settings = FocusSceneSettings.DEFAULT.copy(ambientEnabled = true, volume = .5f)
        assertEquals(.5f, FocusAmbientPolicy.targetVolume(settings, true, true, FocusVoicePhase.IDLE))
        assertEquals(0f, FocusAmbientPolicy.targetVolume(settings, false, true, FocusVoicePhase.IDLE))
        assertEquals(0f, FocusAmbientPolicy.targetVolume(settings, true, false, FocusVoicePhase.IDLE))
    }

    @Test fun liveVoiceDucksAmbientSound() {
        val settings = FocusSceneSettings.DEFAULT.copy(ambientEnabled = true, volume = .5f)
        assertEquals(.09f, FocusAmbientPolicy.targetVolume(settings, true, true, FocusVoicePhase.SPEAKING), .0001f)
        assertEquals(.09f, FocusAmbientPolicy.targetVolume(settings, true, true, FocusVoicePhase.LISTENING), .0001f)
    }
}
```

- [ ] **Step 5: Implement and verify the policy**

```kotlin
object FocusAmbientPolicy {
    private const val VOICE_DUCK_FACTOR = .18f

    fun targetVolume(settings: FocusSceneSettings, sessionRunning: Boolean, appForeground: Boolean, phase: FocusVoicePhase): Float {
        if (!settings.ambientEnabled || !sessionRunning || !appForeground) return 0f
        return if (phase in setOf(FocusVoicePhase.LISTENING, FocusVoicePhase.THINKING, FocusVoicePhase.SPEAKING)) {
            settings.volume * VOICE_DUCK_FACTOR
        } else settings.volume
    }
}
```

Run both new test classes and expect PASS.

- [ ] **Step 6: Commit the scene domain**

```bash
git add android/app/src/main/java/com/example/campusai/data/focus/scene android/app/src/test/java/com/example/campusai/data/focus/scene
git commit -m "feat(android): add focus scene settings and audio policy"
```

---

### Task 2: Original visual and ambient assets

**Files:**
- Create: `android/app/src/main/res/drawable-nodpi/focus_scene_rainy_room.webp`
- Create: `android/app/src/main/res/drawable-nodpi/focus_scene_quiet_library.webp`
- Create: `android/app/src/main/res/drawable-nodpi/focus_scene_forest_morning.webp`
- Create: `android/app/src/main/res/raw/focus_ambient_rainy_room.ogg`
- Create: `android/app/src/main/res/raw/focus_ambient_quiet_library.ogg`
- Create: `android/app/src/main/res/raw/focus_ambient_forest_morning.ogg`

**Interfaces:**
- Produces: six Android resources consumed by `FocusSceneResources` in Task 3.
- Consumes: the composition, originality, and package-size requirements from the spec.

- [ ] **Step 1: Generate the three original vertical backgrounds**

Use Image Gen once per scene with a shared art direction: polished atmospheric digital illustration, portrait Android phone composition, no people, no robot, no typography, no logos, softened central region for UI, darker lower edge for controls. Scene-specific prompts must describe rainy night study room, quiet campus library at dusk, and forest reading nook at morning.

- [ ] **Step 2: Inspect and normalize images**

Open every generated image, reject images containing text/people/robots, then encode each accepted result to 1440×2560 lossless-or-high-quality WebP. Verify with `ffprobe` or ImageMagick that all three have identical dimensions and no animation frames.

- [ ] **Step 3: Generate three procedural loops**

Use ffmpeg lavfi sources and filters only. Each loop must be 30 seconds, stereo, 48 kHz, Vorbis quality 4, with a short equal-power fade at both ends and matched loudness near `-24 LUFS`. Build:

- rain: pink/brown noise layers, high-passed discrete droplet impulses, faint room tone;
- library: low HVAC-shaped noise, very sparse filtered paper-like transients, no voices;
- forest: gently modulated wind/leaf noise plus sparse quiet sine chirps, no recognizable recording.

- [ ] **Step 4: Verify assets**

Run `ffprobe` for codec, channels, sample rate, duration, and dimensions. Confirm each Ogg is 29.9–30.1 seconds, stereo 48 kHz, and each WebP is 1440×2560. Confirm no file originated from the reference repository.

- [ ] **Step 5: Commit original assets**

```bash
git add android/app/src/main/res/drawable-nodpi/focus_scene_*.webp android/app/src/main/res/raw/focus_ambient_*.ogg
git commit -m "feat(android): add original immersive focus assets"
```

---

### Task 3: Audio controller and custom glass backdrop

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/data/focus/scene/FocusAmbientAudioController.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/glass/CampusGlass.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/glass/GlassControlCoverageTest.kt`

**Interfaces:**
- Produces: `FocusAmbientAudioController.setScene(FocusScene)`, `.setTargetVolume(Float)`, and `.release()`; optional `background` content on `CampusGlassScene`.
- Consumes: Media3, generated raw resources, and the existing adaptive glass profile.

- [ ] **Step 1: Add a failing source contract test for custom glass backgrounds**

Add an assertion to `GlassControlCoverageTest` that `CampusGlass.kt` declares `background: (@Composable BoxScope.() -> Unit)? = null` and continues to call `layerBackdrop(backdrop)` exactly on the background layer.

- [ ] **Step 2: Run the glass test and confirm it fails**

Run: `./gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.ui.glass.GlassControlCoverageTest"`

Expected: FAIL because the optional background parameter is absent.

- [ ] **Step 3: Add the backward-compatible custom background**

Update `CampusGlassScene` so its parameter order remains `darkMode`, `modifier`, optional `background`, trailing `content`. Inside the existing `layerBackdrop` box, render `background()` when non-null; otherwise render the current gradient and glows unchanged. All existing trailing-lambda call sites must compile without edits.

- [ ] **Step 4: Implement the Media3 controller**

Map each `FocusScene` to its `R.raw.focus_ambient_*` resource. Configure one `ExoPlayer` with `AudioAttributes` usage `USAGE_MEDIA`, content type `CONTENT_TYPE_MUSIC`, audio focus handling enabled, and `Player.REPEAT_MODE_ONE`. `setScene` must ignore repeated values, load an `android.resource://<package>/<resourceId>` media item, prepare it, and preserve the current target playback state. `setTargetVolume` clamps the value, animates player volume over roughly 220 ms on `Dispatchers.Main.immediate`, plays only above zero, and pauses after fading to zero. `release` cancels the scope and releases the player exactly once.

- [ ] **Step 5: Run glass and ambient policy tests**

Run the targeted test classes from Tasks 1 and 3; expect PASS.

- [ ] **Step 6: Commit controller and glass extension**

```bash
git add android/app/src/main/java/com/example/campusai/data/focus/scene/FocusAmbientAudioController.kt android/app/src/main/java/com/example/campusai/ui/glass/CampusGlass.kt android/app/src/test/java/com/example/campusai/ui/glass/GlassControlCoverageTest.kt
git commit -m "feat(android): connect focus audio to adaptive glass scenes"
```

---

### Task 4: Compose scene experience without robot resets

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/ui/screens/focus/FocusSceneExperience.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/focus/FocusAssistantScreen.kt`
- Test: `android/app/src/test/java/com/example/campusai/ui/screens/focus/FocusSceneContinuityContractTest.kt`

**Interfaces:**
- Produces: `FocusSceneBackdrop`, `FocusSceneToolbar`, `FocusGlassPanel`, and `FocusAmbientPlaybackEffect`.
- Consumes: scene settings, controller, generated resources, `CampusGlassScene`, current `FocusSpaceGuide`, timer, voice phase, and lifecycle state.

- [ ] **Step 1: Write a failing continuity contract test**

The source contract must assert that `FocusSessionScreen` calls `FocusSpaceGuide` outside any `key(sceneSettings.scene)` block, that scene animation is contained inside `FocusSceneBackdrop`, and that the robot image uses `R.drawable.ai_campus_robot`. This protects the user-visible animation continuity from later refactors.

- [ ] **Step 2: Run the continuity test and confirm it fails**

Run: `./gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.ui.screens.focus.FocusSceneContinuityContractTest"`

Expected: FAIL before the scene experience is integrated.

- [ ] **Step 3: Build the focused scene UI units**

`FocusSceneExperience.kt` must provide:

- a `FocusSceneResources` mapping from enum values to background/raw/accent resources;
- `FocusSceneBackdrop` with a scene-keyed background-only crossfade and fixed readability gradients;
- `FocusSceneToolbar` with a scene picker bottom sheet, sound toggle, and volume slider;
- `FocusGlassPanel` using `Modifier.campusGlass(role = CampusGlassRole.PANEL)`;
- `FocusAmbientPlaybackEffect` that remembers one controller, loads persisted settings, applies `FocusAmbientPolicy.targetVolume`, and releases on disposal.

The scene picker must expose all three scene names and subtitles. The sound control must show off/on state before exposing the slider. Every update must save through `FocusScenePreferenceStore`.

- [ ] **Step 4: Integrate the scene as the default active-session layout**

Wrap `FocusSessionScreen` in `CampusGlassScene(darkMode = true, background = { FocusSceneBackdrop(sceneSettings.scene) })`. Place `FocusSceneToolbar`, `FocusSpaceGuide`, timer, controls, and sensing panel in the content layer. Remove the opaque page background and convert timer/guide/sensing containers to local glass panels while preserving accessibility labels and current callbacks.

Keep `FocusSpaceGuide` at the same stable call position. Replace its old full-room `focus_hall_scene` image with the transparent `ai_campus_robot` image, but keep the existing `rememberInfiniteTransition`, floating offset, typewriter message, listening waveform, thinking marker, speaking marker, and interrupt action. Do not include selected scene in any `remember` key inside `FocusSpaceGuide`.

- [ ] **Step 5: Connect runtime playback state**

Pass `focusRunning`, `appForeground`, and `realtimeStatus` to `FocusAmbientPlaybackEffect`. Pausing, backgrounding, disabling sound, or volume zero must target volume zero; voice listening/thinking/speaking must target 18%; idle/connecting must restore user volume. Scene changes update audio independently of the robot.

- [ ] **Step 6: Run the focused contract and unit tests**

Run the scene settings, ambient policy, continuity contract, existing Focus tests, and glass tests. Expect PASS.

- [ ] **Step 7: Commit the immersive focus UI**

```bash
git add android/app/src/main/java/com/example/campusai/ui/screens/focus android/app/src/test/java/com/example/campusai/ui/screens/focus
git commit -m "feat(android): make focus sessions scene immersive"
```

---

### Task 5: Documentation and full verification

**Files:**
- Modify: `android/README.md`
- Modify: `README.md`

**Interfaces:**
- Produces: accurate user/developer documentation and verified Android artifacts.
- Consumes: all prior tasks.

- [ ] **Step 1: Document the Android scene system**

Add a concise section describing the three original scenes, default scene-focus entry, opt-in persistent ambient controls, AI ducking, lifecycle pause, local-only settings, adaptive glass fallback, and robot continuity guarantee. Do not add machine-specific paths.

- [ ] **Step 2: Run targeted tests with bundled JDK 21**

From the repository root in PowerShell:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$env:JAVA_HOME = Join-Path $repoRoot 'android\.tools\jdk21-full\jdk-21.0.12+8'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "$env:JAVA_HOME\bin\java.exe" -version
Set-Location (Join-Path $repoRoot 'android')
.\gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.data.focus.scene.*" --tests "com.example.campusai.ui.screens.focus.FocusSceneContinuityContractTest" --tests "com.example.campusai.ui.glass.*"
```

Expected JDK contains `21.0.12`; all tests PASS.

- [ ] **Step 3: Build the Android debug app**

Run: `.\gradlew.bat :app:assembleDebug`

Expected: `BUILD SUCCESSFUL` and an APK under `android/app/build/outputs/apk/debug/`.

- [ ] **Step 4: Inspect asset and repository hygiene**

Verify image/audio metadata, run `git diff --check`, inspect `git diff`, `git diff --cached`, and `git status --short`, and scan changed lines for secrets, local absolute paths, reference-project asset names, logs, screenshots, or temporary scripts.

- [ ] **Step 5: Commit documentation and verification-ready state**

```bash
git add README.md android/README.md
git commit -m "docs(android): document immersive focus scenes"
```

- [ ] **Step 6: Final review**

Review the full branch diff from commit `270148c5` to `HEAD`, confirm the robot continuity contract and audio lifecycle requirements are represented in code and tests, and report any verification that could not be run.

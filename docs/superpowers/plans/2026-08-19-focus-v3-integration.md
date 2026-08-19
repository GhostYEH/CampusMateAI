# Focus V3 Integration Plan

> **For agentic workers:** Execute this plan inline in the current task with incremental verification after each slice.

**Goal:** Integrate the completed V3.2 learning-state and V3.3 Presence/local-vision capabilities into the latest `master` architecture without regressing its UI, navigation, repositories, APIs, or data model.

**Architecture:** Start from the fetched `master` tip and migrate only the behavior/presence implementation, model assets, camera-pipeline hooks, tests, and the required semantic changes to Focus and expression-session code. Resolve the three high-risk files by preserving `master` as the product baseline and carrying over only compatible feature behavior.

**Tech Stack:** Android/Kotlin, Jetpack Compose, Gradle Kotlin DSL, ONNX Runtime, TensorFlow Lite, JUnit.

**Spec:** User request in the current Codex task.

## Global Constraints

- Use the bundled JDK 21.0.12+8 for all Android build/test commands.
- `master` is authoritative for current UI, Navigation, Repository, API, and data structures.
- Do not migrate legacy README/documentation changes before code integration is complete.
- Do not modify unrelated code or perform unrelated UI refactors.

---

### Task 1: Establish branch and migration inventory

**Files:**
- Create: `docs/superpowers/plans/2026-08-19-focus-v3-integration.md`
- Modify: none in product code

- [x] Confirm fetched refs, exact branch relationships, and the requested feature commits.
- [x] Create `integration/focus-v3` from the fetched `master` tip.
- [x] Inventory feature-only files and the `FocusScreen.kt`, `ExpressionSessionManager.kt`, and `build.gradle.kts` diffs before applying changes.

### Task 2: Migrate behavior, continuity, history, Presence, and local models

**Files:**
- Modify/create only the Android behavior package files identified by the inventory.
- Add the required ONNX/TFLite model assets and model metadata.
- Add the behavior and Presence unit tests from the feature branch, adapting imports/contracts to `master` where required.

- [x] Preserve master V3.1 `VISIBLE_STUDY`/`IDLE`, `BehaviorSignalProcessor`, `LearningContinuityStateMachine`, and `BehaviorObservationHistory`, then enable the V3.2 ONNX model.
- [x] Port ONNX V3.2 local behavior recognition and the person detector/`PersonAnalyzer`.
- [x] Port V3.3 Presence state handling, camera-pipeline wiring, assets, and tests.
- [x] Run focused behavior tests and fix only integration-caused issues.

### Task 3: Semantically merge expression/session and Focus UI behavior

**Files:**
- Modify: `android/app/src/main/java/**/data/expression/ExpressionSessionManager.kt`
- Modify: `android/app/src/main/java/**/ui/screens/focus/FocusScreen.kt`

- [x] Preserve the latest `master` Focus layout, navigation, repositories, and data contracts.
- [x] Add current learning state, Presence, expression assistance, recent learning rhythm, and the current observation summary using the migrated feature APIs.
- [x] Preserve lifecycle/disposal behavior in `ExpressionSessionManager` while adding compatible feature session data.
- [x] Add/update focused tests where existing contracts permit it.

### Task 4: Integrate build configuration and verify the product slice

**Files:**
- Modify: `android/app/build.gradle.kts`
- Modify: `android/gradle/libs.versions.toml`
- Modify final documentation only if it accurately reflects the integrated implementation.

- [x] Merge dependency/plugin/model configuration semantically, retaining current `master` settings unless required by the migrated capabilities.
- [x] Run Android compilation and existing relevant tests with bundled JDK 21.
- [x] Review the final diff for unrelated changes, record conflicts and resolutions, and report branch cleanup candidates.

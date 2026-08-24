# V3.4 Android / HarmonyOS deployment verification (2026-08-24)

## Runtime contract

- Android loads `campusmate_behavior_v34.onnx` first and uses the latest person box as a 10%-expanded ROI.
- Android falls back to packaged V3.2 when V3.4 initialization fails or a person ROI is unavailable.
- HarmonyOS packages the equivalent MindIR Lite model and connects CameraKit preview frames to an ImageReceiver, CoreVision person detection, RGBA conversion, and the local ROI inference provider.
- HarmonyOS prefers the front camera, accepts only CoreVision label `13` with score `>= 0.50`, and analyzes at most one frame per second. It never sends images to the backend or substitutes the full frame when a person box is absent.
- Camera capture starts only after the user starts or resumes a study-focus timer; short and long breaks never start behavior recognition. Pause, finish, back navigation, and page disappearance invalidate an in-progress start and release the receiver, camera session, input, output, detector, and per-frame image resources.
- Both platforms use output order `READ`, `WRITE`, `PHONE_INTERACTION`, `NO_VISIBLE_STUDY`, temperature `4.841172366232762`, confidence `0.30`, and margin `0.05`.

## MindSpore Lite conversion finding

The official HarmonyOS conversion guide points to MindSpore Lite 2.1.0. Its ONNX parser accepted the 19 `HardSwish` nodes in this MobileNetV3 graph, but the resulting model produced invalid output magnitudes. The deployment preparation script therefore expands each `HardSwish(x)` into the mathematically equivalent `x * HardSigmoid(x, alpha=1/6, beta=0.5)` before conversion and uses `--optimize=none`.

Hashes:

- Training/export ONNX: `9abe029d18e1bfc1f0e1e47217f575153af966bf013500dd66e8dda0592c5740`
- MindSpore-compatible ONNX graph: `8ff821cfa506c47ba96da75750e5bf09e3ec5029a2093d38715cfe11367b8cf9`
- MindIR Lite: `b1c40c708ae1c2ad75273765b923cf2330a41469fd711dd36059c52d84071b2f`

For deterministic seed `20260824`, ONNX Runtime returned logits `[-0.7301855, 0.10601026, 0.44252688, 0.3313881]`. MindSpore Lite benchmark returned `[-0.730186, 0.10601, 0.442527, 0.331388]` and reported mean bias `0%` with accuracy threshold `0.0001`.

## Build evidence

- Android bundled JDK: OpenJDK `21.0.12+8`.
- Android `:app:testDebugUnitTest :app:assembleDebug`: successful.
- APK contains both `assets/models/behavior/campusmate_behavior_v34.onnx` and `campusmate_visible_study_v32.onnx`.
- HarmonyOS `assembleHap`: successful after the camera/person-ROI pipeline was wired; HAP contains `campusmate_behavior_v34.ms` and `model_card.json`.
- Host contract tests: 6 passed, covering person filtering/selection, non-finite and boundary rejection, break-mode suppression, one-second/in-flight frame dropping, fail-closed UI state, and start/stop race invalidation.
- ArkTS decision/reminder Hypium tests were added under `entry/src/test`. The repository's declared `ohosTest` target currently lacks `entry/src/ohosTest/module.json5`, so Hvigor cannot execute that test target without adding the project's missing test runner scaffold.

## Deliberately unverified

Real-device camera delivery, preview rotation, RGBA channel order, person-box alignment, CoreVision model availability, runtime latency, battery use, thermal behavior, and end-to-end reminder timing were not tested in this iteration, as requested. CoreVision multi-object recognition is documented as unsupported on the simulator, so these checks require a supported HarmonyOS phone.

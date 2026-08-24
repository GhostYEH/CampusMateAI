# V3.4 Android / HarmonyOS deployment verification (2026-08-24)

## Runtime contract

- Android loads `campusmate_behavior_v34.onnx` first and uses the latest person box as a 10%-expanded ROI.
- Android falls back to packaged V3.2 when V3.4 initialization fails or a person ROI is unavailable.
- HarmonyOS packages the equivalent MindIR Lite model and exposes a local RGBA + person-box inference provider.
- HarmonyOS explicitly reports unavailable until its camera/person-ROI pipeline supplies a valid frame; it never sends images to the backend or substitutes the full frame.
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
- HarmonyOS `assembleHap`: successful; HAP contains `campusmate_behavior_v34.ms` and `model_card.json`.
- ArkTS decision/reminder Hypium tests were added under `entry/src/test`. The repository's declared `ohosTest` target currently lacks `entry/src/ohosTest/module.json5`, so Hvigor cannot execute that test target without adding the project's missing test runner scaffold.

## Deliberately unverified

Real-device camera delivery, person-box alignment, runtime latency, battery use, thermal behavior, and end-to-end reminder timing were not tested in this iteration, as requested.

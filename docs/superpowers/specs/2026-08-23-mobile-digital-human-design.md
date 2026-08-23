# Mobile Digital Human Design

## Goal

Bring the verified CampusMate Unity digital human to the Android and HarmonyOS counselor screens, including automatic MiMo speech playback, synchronized mouth motion, blinking, and subtle head motion.

## Chosen architecture

Use the existing Unity WebGL build as the single visual runtime and host it from the authenticated CampusMate backend origin. Android renders it with a hardware-accelerated WebView; HarmonyOS renders it with ArkWeb. A mobile host page owns the PCM stream player and forwards the real playback level to Unity on every animation frame.

This is the highest-fidelity implementation that can be built and verified with the installed toolchain. The installed Unity editor only has WebGL support, and no Tuanjie/Harmony native engine toolchain is present. Reusing the verified WebGL build also prevents platform-specific mouth, blink, and head-motion behavior from drifting.

## Runtime flow

1. The counselor page loads `/digital-human/mobile.html` from the API host.
2. Native code injects the current API base URL and short-lived access token into the page's in-memory JavaScript API.
3. When an assistant stream completes, native code sends the final answer to the page.
4. The page calls `POST /api/v1/assistant/tts` and streams PCM16LE at 24 kHz.
5. Web Audio schedules PCM chunks with a short buffer and samples the actual output level.
6. The page posts `speech-level` and `speech-state` messages to the Unity frame.
7. Unity drives the `VRC.v_aa` mouth blendshape from that live level. Existing Unity logic continues blinking and subtle head movement.

## User experience

- The large digital-human stage replaces the small static counselor hero.
- Successful assistant answers are read automatically.
- The stage provides mute, stop, and replay controls.
- Loading, ready, speaking, user-gesture-required, and error states are visible.
- Text chat remains usable if the visual or speech service fails.
- Reduced-motion remains respected by native page transitions; speech-driven mouth animation remains active because it communicates audio content.

## Security

- Provider keys never enter Android, HarmonyOS, URLs, HTML, or logs.
- The mobile page receives only the current user access token in JavaScript memory.
- The access token is not persisted by the page and is not placed in a query string or fragment.
- The TTS route remains authenticated and strips Markdown server-side.
- Digital-human static assets are read-only. Large Unity build artifacts use a one-day cache because their filenames are stable rather than content-hashed; HTML and control scripts revalidate.

## Failure handling

- A failed Unity load shows a clear visual fallback while chat continues.
- A failed TTS request reports that text is still available and resets the mouth to closed.
- Starting a new answer cancels current synthesis/playback before speaking the new answer.
- Leaving the page stops audio and resets Unity speech state.

## Verification

- Unit-test mobile URL derivation and page command encoding.
- Unit-test/static-test the backend asset mount and cache headers.
- Run web audio tests and a browser smoke test of the hosted mobile page.
- Build and unit-test Android with the repository-mandated JDK 21.
- Build HarmonyOS with the repository hvigor wrapper.
- Confirm the page sends non-zero speech levels only while PCM is actually playing.

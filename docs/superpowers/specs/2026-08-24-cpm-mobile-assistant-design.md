# CPM Mobile Assistant Design

## Product brief

Rebuild the existing Android and HarmonyOS AI assistant tab as CPM, using the supplied 944 x 1668 mobile reference as the visual target. The result is a fully interactive native experience: a calm white/lavender home state, a live digital-human card, growth-oriented prompts, and a compact ChatGPT-like conversation state with token-level streaming and independently queued speech.

## Product states

The page has two explicit states.

1. **Welcome** shows `CPM ✦`, `校园问题，随时来聊一聊`, the large digital-human card, recommendations, and the composer.
2. **Conversation** begins as soon as a prompt is submitted. Recommendations fade out, the full digital-human card remains visible, and the message list expands above the composer.

The old `AI 校园助手`, `真实后端`, orange/green status indicators, and capability-tag row are removed. Both bottom navigation bars use `CPM`.

## Visual system

- White-to-lavender page gradient with a dark-mode equivalent.
- 24-32 dp/vp card radii, pale indigo borders, soft low-opacity shadows, and translucent surfaces.
- Live digital human clipped into an enlarged circular lavender viewport on the left; native title and playback controls on the right. The crop prioritizes the face while retaining both sleeves and hands.
- `你好，我是CPM` uses a blue-to-violet text brush where supported and CPM brand blue as a safe fallback.
- User messages use a blue-violet gradient, assistant messages use white/translucent surfaces.
- Existing platform icon systems are used for functional icons; the existing live digital-human asset remains the hero asset.

## Shared conversation contract

Every message has `id`, `role`, `content`, and `status`, where status is `GENERATING`, `COMPLETED`, or `ERROR`. Submission appends the user message and an empty generating assistant message immediately. Each SSE chunk appends to the existing assistant message. Completion changes only its status; an error preserves partial text when present and marks the message as failed.

Recommendations are provided by a swappable catalog and shuffled in batches of four. Initial content focuses on student growth: first-year planning, graduate study versus employment, choosing clubs, and balancing study and life.

## Android architecture

`CounselorViewModel` owns a `StateFlow<CpmCounselorUiState>` and accepts a streaming function backed by `AppRepository.streamChat`. Compose observes state lifecycle-aware, renders a lazy message list, and sends user intents to the ViewModel. The ViewModel persists through configuration changes and exposes a separate completed-speech event for the digital-human TTS bridge.

The live WebView remains mounted across welcome/conversation transitions. Native mute, pause, and replay buttons call a small JavaScript bridge. The WebView uses embedded visual mode so its duplicate web header and controls are hidden.

The Unity idle loop combines continuous breathing and head/neck motion with randomized left-hand, right-hand, and two-hand gestures. Natural blinking and a low-amplitude friendly expression are scheduled independently. Speech reduces gesture intensity so idle motion never fights lip sync.

## HarmonyOS architecture

`CpmChatDataSource` owns `@Observed` message objects and emits indexed `LazyForEach` change notifications. `Index.ets` writes every SSE chunk into this source, fixing the stale plain-array/`ForEach` update path. `CounselorPage` receives the data source and uses `LazyForEach`; component state controls welcome/conversation transitions with `animateTo`.

TTS remains completion-driven and separate from streaming UI state: chunks update the data source only, while a completed answer advances the speech request queue. Playback controls call the digital-human Web API without mutating chat state.

## Error and lifecycle behavior

- Empty streams become an `ERROR` assistant bubble with a retry action.
- Partial streams retain visible partial text and display an error status.
- Duplicate submissions are blocked while generating.
- Digital-human WebViews stop audio and release resources when their page disappears.
- Replay uses the most recently completed answer; mute and pause never block text rendering.

## Verification

- Unit-test message reducer/data-source semantics: immediate empty bubble, ordered chunk append, completion, and error retention.
- Unit-test digital-human bridge scripts including embed mode and playback commands.
- Build Android with bundled JDK 21 and run relevant unit tests plus debug APK assembly.
- Build HarmonyOS ArkTS/HAP and run available tests/build checks.
- Search both mobile source trees for banned old labels and verify bottom nav shows CPM.

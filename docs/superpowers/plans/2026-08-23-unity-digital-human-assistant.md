# Unity Digital Human Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the Rusk Unity digital human in CampusMate AI, speak DeepSeek answers with MiMo V2.5 TTS “冰糖”, and add synchronized mouth, blink, and restrained head/neck motion.

**Architecture:** FastAPI remains the only holder of provider credentials and streams MiMo PCM16 audio to the Vue client. Vue streams chat text, schedules PCM16 through Web Audio, and sends speech state/level messages to an embedded Unity WebGL iframe. Unity receives those messages, drives the existing facial BlendShapes, and adds bounded procedural Head/Neck motion.

**Tech Stack:** FastAPI, Pydantic Settings, httpx, pytest, Vue 3, Vite, browser Web Audio API, Node test runner, Unity 6.3, C#, Unity Test Framework, WebGL.

**Spec:** `docs/superpowers/specs/2026-08-23-unity-digital-human-assistant-design.md`

## Global Constraints

- DeepSeek uses `https://api.deepseek.com` and `deepseek-v4-flash` in non-thinking mode.
- MiMo uses `https://api.xiaomimimo.com/v1`, `mimo-v2.5-tts`, voice `冰糖`, and 24 kHz mono PCM16LE.
- Real provider keys exist only in untracked `backend/.env`; examples contain placeholders only.
- TTS failure never removes or blocks the text answer.
- Head rotation is additive from cached local rotations and cannot accumulate drift.
- Generated WebGL output is verified locally but is not mixed into source-code commits unless the repository explicitly tracks it.
- Preserve all unrelated dirty-worktree changes; stage only files owned by each task.

---

### Task 1: DeepSeek and MiMo configuration contract

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`
- Modify locally only: `backend/.env`
- Test: `backend/tests/test_tts_config.py`

**Interfaces:**
- Produces: `Settings.mimo_tts_available: bool`, plus `mimo_base_url`, `mimo_api_key`, `mimo_tts_model`, `mimo_tts_voice`, `mimo_tts_timeout_seconds`, and `mimo_tts_max_chars`.
- Produces: DeepSeek settings with `llm_model="deepseek-v4-flash"` in local `.env`.

- [ ] **Step 1: Write failing configuration tests**

```python
from app.core.config import Settings


def test_mimo_tts_available_requires_complete_credentials():
    assert not Settings(mimo_api_key="").mimo_tts_available
    settings = Settings(mimo_api_key="test-key")
    assert settings.mimo_tts_available
    assert settings.mimo_tts_model == "mimo-v2.5-tts"
    assert settings.mimo_tts_voice == "冰糖"
    assert settings.mimo_tts_sample_rate == 24000
```

- [ ] **Step 2: Run the test and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tts_config.py -q`

Expected: FAIL because the MiMo fields and `mimo_tts_available` do not exist.

- [ ] **Step 3: Add the minimal typed settings and safe examples**

```python
mimo_base_url: str = "https://api.xiaomimimo.com/v1"
mimo_api_key: str = ""
mimo_tts_model: str = "mimo-v2.5-tts"
mimo_tts_voice: str = "冰糖"
mimo_tts_timeout_seconds: int = 60
mimo_tts_max_chars: int = 4000
mimo_tts_sample_rate: int = 24000

@property
def mimo_tts_available(self) -> bool:
    return bool(self.mimo_base_url and self.mimo_api_key and self.mimo_tts_model)
```

Add placeholder-only MiMo variables to `.env.example`. Put the two user-provided keys only into the already ignored `backend/.env`, using `LLM_API_KEY` and `MIMO_API_KEY`; do not print the values.

- [ ] **Step 4: Run the focused test and inspect the diff for secrets**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tts_config.py -q`

Run: `git diff -- backend/app/core/config.py backend/.env.example backend/tests/test_tts_config.py`

Expected: PASS; no real key appears in the diff.

- [ ] **Step 5: Commit the configuration contract**

```powershell
git add backend/app/core/config.py backend/.env.example backend/tests/test_tts_config.py
git commit -m "feat: define DeepSeek and MiMo runtime configuration"
```

### Task 2: MiMo streaming TTS client

**Files:**
- Create: `backend/app/services/tts/__init__.py`
- Create: `backend/app/services/tts/mimo.py`
- Test: `backend/tests/test_mimo_tts.py`

**Interfaces:**
- Consumes: MiMo fields from `Settings`.
- Produces: `strip_speech_markdown(text: str) -> str`.
- Produces: `MiMoTtsClient.stream_pcm(text: str, style: str = "") -> AsyncIterator[bytes]` and `aclose() -> None`.
- Produces: `TtsError`, `TtsTimeoutError`, and `TtsConfigError` without credential-bearing messages.

- [ ] **Step 1: Write failing request and stream parser tests**

```python
@pytest.mark.asyncio
async def test_stream_pcm_sends_assistant_text_and_bingtang_voice():
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"audio":{"data":"AQI="}}}]}\n\n'
                 'data: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )

    client = MiMoTtsClient(
        base_url="https://api.xiaomimimo.com/v1",
        api_key="test",
        model="mimo-v2.5-tts",
        voice="冰糖",
        transport=httpx.MockTransport(handler),
    )
    chunks = [chunk async for chunk in client.stream_pcm("你好")]
    assert chunks == [b"\x01\x02"]
    assert captured["payload"]["messages"][-1] == {"role": "assistant", "content": "你好"}
    assert captured["payload"]["audio"] == {"format": "pcm16", "voice": "冰糖"}
```

- [ ] **Step 2: Run and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_mimo_tts.py -q`

Expected: FAIL because `app.services.tts.mimo` does not exist.

- [ ] **Step 3: Implement the minimal streaming client**

```python
payload = {
    "model": self._model,
    "messages": ([{"role": "user", "content": style}] if style else [])
        + [{"role": "assistant", "content": text}],
    "audio": {"format": "pcm16", "voice": self._voice},
    "stream": True,
}
async with client.stream("POST", "/chat/completions", json=payload) as response:
    response.raise_for_status()
    async for line in response.aiter_lines():
        if not line.startswith("data:"):
            continue
        value = line[5:].strip()
        if value == "[DONE]":
            break
        audio = json.loads(value).get("choices", [{}])[0].get("delta", {}).get("audio")
        if isinstance(audio, dict) and audio.get("data"):
            yield base64.b64decode(audio["data"], validate=True)
```

Translate timeout, HTTP, JSON, and Base64 errors into the TTS error types without including the API key or full upstream body.

- [ ] **Step 4: Run focused tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_mimo_tts.py -q`

Expected: request contract, multiple audio chunks, malformed SSE, timeout, and Markdown stripping tests all PASS.

- [ ] **Step 5: Commit the client**

```powershell
git add backend/app/services/tts backend/tests/test_mimo_tts.py
git commit -m "feat: stream MiMo PCM speech"
```

### Task 3: Authenticated TTS API and lifecycle

**Files:**
- Create: `backend/app/schemas/tts.py`
- Create: `backend/app/api/routes/tts.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/services/container.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tts_route.py`

**Interfaces:**
- Consumes: `MiMoTtsClient.stream_pcm` and `Settings.mimo_tts_max_chars`.
- Produces: `POST /api/v1/assistant/tts` with JSON `{ "text": str, "style": str | null }`.
- Produces: streaming response `application/octet-stream` with `X-Audio-Format: pcm16le`, `X-Audio-Sample-Rate: 24000`, and `X-Audio-Channels: 1`.

- [ ] **Step 1: Write failing route tests**

```python
def test_tts_requires_login(client):
    response = client.post("/api/v1/assistant/tts", json={"text": "你好"})
    assert response.status_code == 401


def test_tts_streams_pcm_with_metadata(authenticated_client, fake_tts):
    response = authenticated_client.post("/api/v1/assistant/tts", json={"text": "你好"})
    assert response.status_code == 200
    assert response.content == b"\x01\x02\x03\x04"
    assert response.headers["x-audio-sample-rate"] == "24000"
```

Also test empty text, over-limit text, unconfigured TTS, upstream failure, and cancellation cleanup.

- [ ] **Step 2: Run and verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tts_route.py -q`

Expected: FAIL with route not found.

- [ ] **Step 3: Implement schema, route, container ownership, and shutdown**

```python
class TtsRequest(BaseModel):
    text: str = Field(min_length=1)
    style: str | None = Field(default=None, max_length=500)


@router.post("/assistant/tts")
async def synthesize_speech(
    req: TtsRequest,
    _: UserRow = Depends(current_user),
    container: ServiceContainer = Depends(get_container),
):
    text = strip_speech_markdown(req.text)
    if len(text) > container.settings.mimo_tts_max_chars:
        raise HTTPException(status_code=422, detail="朗读文本过长")
    if container.tts is None:
        raise HTTPException(status_code=503, detail="语音服务未配置")
    return StreamingResponse(
        container.tts.stream_pcm(text, req.style or ""),
        media_type="application/octet-stream",
        headers={"X-Audio-Format": "pcm16le", "X-Audio-Sample-Rate": "24000", "X-Audio-Channels": "1"},
    )
```

Build one TTS client per service container and close it in FastAPI shutdown alongside the LLM client.

- [ ] **Step 4: Run route and regression tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tts_route.py backend/tests/test_llm.py backend/tests/test_counselor.py -q`

Expected: all selected tests PASS.

- [ ] **Step 5: Commit the endpoint**

```powershell
git add backend/app/schemas/tts.py backend/app/api/routes/tts.py backend/app/api/router.py backend/app/services/container.py backend/app/main.py backend/tests/test_tts_route.py
git commit -m "feat: expose authenticated assistant speech stream"
```

### Task 4: Browser PCM player and Unity message bridge

**Files:**
- Create: `web/src/features/digitalHuman/speechText.js`
- Create: `web/src/features/digitalHuman/pcmPlayer.js`
- Create: `web/src/features/digitalHuman/unityBridge.js`
- Create: `web/src/features/digitalHuman/digitalHumanAudio.test.js`
- Modify: `web/package.json`

**Interfaces:**
- Produces: `normalizeSpeechText(markdown: string) -> string`.
- Produces: `PcmStreamPlayer({ sampleRate, onLevel, onState })` with `append(Uint8Array)`, `finish()`, and `stop()`.
- Produces: `createUnityBridge(iframe)` with `setSpeaking(bool)`, `setSpeechLevel(number)`, and `stop()` using `window.postMessage`.

- [ ] **Step 1: Add Node tests for pure audio helpers**

```javascript
import test from "node:test";
import assert from "node:assert/strict";
import { normalizeSpeechText } from "./speechText.js";
import { pcm16ToFloat32, rmsLevel } from "./pcmPlayer.js";

test("normalizes markdown for speech", () => {
  assert.equal(normalizeSpeechText("**你好** [教务处](https://example.test)"), "你好 教务处");
});

test("converts little-endian pcm16 and clamps rms", () => {
  const samples = pcm16ToFloat32(new Uint8Array([0xff, 0x7f, 0x00, 0x80]));
  assert.ok(samples[0] > 0.99 && samples[1] === -1);
  assert.ok(rmsLevel(samples) > 0.9);
});
```

Add `"test": "node --test src/features/**/*.test.js"` to `web/package.json`.

- [ ] **Step 2: Run and verify RED**

Run: `npm test --prefix web`

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement pure conversion, player scheduling, cancellation, and bridge messages**

```javascript
export function pcm16ToFloat32(bytes) {
  const count = Math.floor(bytes.byteLength / 2);
  const out = new Float32Array(count);
  const view = new DataView(bytes.buffer, bytes.byteOffset, count * 2);
  for (let i = 0; i < count; i += 1) out[i] = Math.max(-1, view.getInt16(i * 2, true) / 32768);
  return out;
}

export function createUnityBridge(iframe) {
  const send = (type, value) => iframe?.contentWindow?.postMessage({ source: "campusmate", type, value }, location.origin);
  return {
    setSpeaking: (value) => send("speech-state", Boolean(value)),
    setSpeechLevel: (value) => send("speech-level", Math.max(0, Math.min(1, Number(value) || 0))),
    stop: () => send("speech-stop", true),
  };
}
```

Keep AudioContext creation lazy so it happens after a user interaction. Schedule each buffer at `max(context.currentTime, nextStartTime)` and cancel scheduled sources in `stop()`.

- [ ] **Step 4: Run tests and Web build**

Run: `npm test --prefix web`

Run: `npm run build --prefix web`

Expected: tests PASS and Vite build exits 0.

- [ ] **Step 5: Commit browser audio primitives**

```powershell
git add web/package.json web/src/features/digitalHuman
git commit -m "feat: add streaming PCM and Unity bridge primitives"
```

### Task 5: Campus assistant digital human panel

**Files:**
- Create: `web/src/components/counselor/DigitalHumanPanel.vue`
- Modify: `web/src/services/api.js`
- Modify: `web/src/views/student/StudentCounselorView.vue`
- Modify: `web/src/styles/student-pages.css`
- Test: `web/src/features/digitalHuman/digitalHumanAudio.test.js`

**Interfaces:**
- Consumes: `PcmStreamPlayer`, `normalizeSpeechText`, `createUnityBridge`.
- Produces: `streamAssistantSpeech(text, { signal, onChunk, onHeaders })` in `api.js`.
- Produces: `DigitalHumanPanel` props `speaking`, `muted`, `available`; emits `toggle-muted`, `stop`, `replay`, and `ready`.

- [ ] **Step 1: Extend failing tests for fetch streaming and bridge state**

```javascript
test("unity bridge clamps speech level", () => {
  const sent = [];
  const iframe = { contentWindow: { postMessage: (message) => sent.push(message) } };
  createUnityBridge(iframe).setSpeechLevel(3);
  assert.equal(sent[0].value, 1);
});
```

- [ ] **Step 2: Run and verify RED**

Run: `npm test --prefix web`

Expected: FAIL until bridge and stream behavior match the contract.

- [ ] **Step 3: Implement TTS fetch, panel, and chat lifecycle integration**

```javascript
export async function streamAssistantSpeech(text, { signal, onChunk, onHeaders } = {}) {
  const token = localStorage.getItem("campus_access_token");
  const response = await fetch(`${BASE_URL}/assistant/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ text }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error(`语音服务错误 (${response.status})`);
  onHeaders?.(response.headers);
  const reader = response.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk?.(value);
  }
}
```

On chat `onDone`, speak `pending.text` when auto-speech is enabled. Starting a new question, changing session, route unmount, or clicking stop aborts the previous TTS and stops scheduled audio. Persist mute preference under `campus_digital_human_muted`.

Replace the static right-side promo with `DigitalHumanPanel`, retain the static image as its loading/error fallback, and add desktop/compact responsive styles.

- [ ] **Step 4: Run tests and build**

Run: `npm test --prefix web`

Run: `npm run build --prefix web`

Expected: all tests PASS; build exits 0 without Vue compiler errors.

- [ ] **Step 5: Commit the UI integration**

```powershell
git add web/src/components/counselor/DigitalHumanPanel.vue web/src/services/api.js web/src/views/student/StudentCounselorView.vue web/src/styles/student-pages.css web/src/features/digitalHuman/digitalHumanAudio.test.js
git commit -m "feat: embed the speaking digital human in counselor chat"
```

### Task 6: Unity external speech and natural head motion

**Files (Unity project `D:/File/数字人/数字人`):**
- Modify: `Assets/Scripts/RuskDigitalHuman.cs`
- Create: `Assets/Scripts/RuskHeadMotion.cs`
- Create: `Assets/Tests/EditMode/DigitalHuman.EditMode.asmdef`
- Create: `Assets/Tests/EditMode/RuskDigitalHumanTests.cs`
- Create: `Assets/Tests/EditMode/RuskHeadMotionTests.cs`

**Interfaces:**
- Produces on the Rusk root GameObject: `SetSpeechLevel(string value)`, `SetSpeaking(string value)`, and `StopSpeech()` for JavaScript `SendMessage`.
- Produces: `RuskHeadMotion.Configure(Transform head, Transform neck)` and bounded additive motion driven by `SetSpeechLevel(float)` / `SetSpeaking(bool)`.
- Consumes: existing `Body` face renderer and `Head` / `Neck` hierarchy.

- [ ] **Step 1: Add failing EditMode tests**

```csharp
[Test]
public void ExternalSpeechLevelIsClamped()
{
    var go = new GameObject("Rusk");
    var digitalHuman = go.AddComponent<RuskDigitalHuman>();
    digitalHuman.SetSpeechLevel("3.5");
    Assert.That(digitalHuman.CurrentSpeechLevel, Is.EqualTo(1f));
}

[Test]
public void HeadTargetNeverExceedsConfiguredAngles()
{
    var sample = RuskHeadMotion.ClampEuler(new Vector3(20f, -20f, 20f), new Vector3(4f, 4f, 2f));
    Assert.That(Mathf.Abs(sample.x), Is.LessThanOrEqualTo(4f));
    Assert.That(Mathf.Abs(sample.y), Is.LessThanOrEqualTo(4f));
    Assert.That(Mathf.Abs(sample.z), Is.LessThanOrEqualTo(2f));
}
```

- [ ] **Step 2: Run Unity EditMode tests and verify RED**

Run through Unity MCP `run_tests(mode="EditMode")` after confirming `mcpforunity://editor/state` reports ready.

Expected: FAIL because the external speech and head-motion APIs do not exist.

- [ ] **Step 3: Implement external mouth level and bounded Head/Neck motion**

```csharp
public void SetSpeechLevel(string value)
{
    if (float.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var parsed))
        externalSpeechLevel = Mathf.Clamp01(parsed);
}

private void LateUpdate()
{
    var idle = SampleIdle(Time.time);
    var speechNod = isSpeaking ? Mathf.Sin(Time.time * speakingFrequency) * speechLevel * speakingPitch : 0f;
    head.localRotation = headBaseRotation * Quaternion.Euler(idle.x + speechNod, idle.y, idle.z);
    neck.localRotation = neckBaseRotation * Quaternion.Euler((idle.x + speechNod) * neckShare, idle.y * neckShare, idle.z * neckShare);
}
```

Use damped target values, randomized target intervals, and base-rotation multiplication. Do not modify transforms when references are missing; log one bounded warning rather than one warning per frame.

- [ ] **Step 4: Compile, inspect console, and run tests**

Read `mcpforunity://editor/state` until `data.compilation.is_compiling == false`, then run `read_console(types=["error"], include_stacktrace=true)` and Unity EditMode tests.

Expected: no compile errors and all EditMode tests PASS.

- [ ] **Step 5: Attach and configure through Unity MCP**

Find the Rusk root and Head/Neck objects with `find_gameobjects`, add `RuskHeadMotion`, assign references, and set conservative defaults: head max `(3.5, 4.0, 1.5)`, neck share `0.45`, speaking pitch `1.2`.

Save `Assets/Scenes/SampleScene.unity`, enter Play Mode, and verify through screenshot plus console that the model remains correctly posed.

### Task 7: WebGL bridge template and build

**Files (Unity project `D:/File/数字人/数字人`):**
- Create: `Assets/WebGLTemplates/CampusMate/index.html`
- Create: `Assets/WebGLTemplates/CampusMate/TemplateData/style.css`
- Create: `Assets/Editor/CampusMateWebGLBuild.cs`
- Generated locally: `D:/File/demo1/web/public/digital-human/`

**Interfaces:**
- Consumes parent messages `{ source: "campusmate", type: "speech-state" | "speech-level" | "speech-stop", value }`.
- Calls Unity GameObject `Rusk` methods `SetSpeaking`, `SetSpeechLevel`, and `StopSpeech`.
- Posts `{ source: "campusmate-unity", type: "ready" | "error" }` to the parent page.

- [ ] **Step 1: Add bridge contract to the custom WebGL template**

```javascript
window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin || event.data?.source !== "campusmate" || !unityInstance) return;
  if (event.data.type === "speech-level") unityInstance.SendMessage("Rusk", "SetSpeechLevel", String(event.data.value));
  if (event.data.type === "speech-state") unityInstance.SendMessage("Rusk", "SetSpeaking", String(Boolean(event.data.value)));
  if (event.data.type === "speech-stop") unityInstance.SendMessage("Rusk", "StopSpeech");
});
```

Configure the template for a transparent full-size canvas and post `ready` only after `createUnityInstance` resolves.

- [ ] **Step 2: Add deterministic editor build entry point**

```csharp
[MenuItem("CampusMate/Build WebGL Digital Human")]
public static void Build()
{
    PlayerSettings.WebGL.template = "PROJECT:CampusMate";
    PlayerSettings.runInBackground = true;
    var output = Environment.GetEnvironmentVariable("CAMPUSMATE_WEBGL_OUTPUT")
        ?? "D:/File/demo1/web/public/digital-human";
    BuildPipeline.BuildPlayer(new[] { "Assets/Scenes/SampleScene.unity" }, output, BuildTarget.WebGL, BuildOptions.None);
}
```

- [ ] **Step 3: Compile and inspect Unity console**

Wait for compilation, then run `read_console(types=["error"], include_stacktrace=true)`.

Expected: no compiler errors and the `CampusMate/Build WebGL Digital Human` menu item exists.

- [ ] **Step 4: Build WebGL with Unity MCP or batch-mode fallback**

Preferred: execute the verified menu item via Unity MCP after reading `mcpforunity://menu-items`.

Fallback: invoke the installed Unity editor with `-batchmode -quit -projectPath D:/File/数字人/数字人 -executeMethod CampusMateWebGLBuild.Build -logFile <local-log>`.

Expected: `web/public/digital-human/index.html` and loader/data/framework/wasm files exist; build log contains `Build completed` and no errors.

- [ ] **Step 5: Verify source security**

Run: `Get-ChildItem -Recurse -File 'web/public/digital-human' | Select-String -Pattern 'sk-[A-Za-z0-9]{16,}'`

Expected: no matches.

### Task 8: End-to-end verification and delivery hygiene

**Files:**
- Modify: `backend/README.md`
- Modify: `web/README.md`
- No generated screenshots or logs are committed.

**Interfaces:**
- Consumes all previous tasks.
- Produces a verified local CampusMate assistant with text, speech, mouth, and head motion.

- [ ] **Step 1: Run backend focused and full tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_tts_config.py backend/tests/test_mimo_tts.py backend/tests/test_tts_route.py backend/tests/test_llm.py backend/tests/test_counselor.py -q`

Then run: `backend/.venv/Scripts/python.exe -m pytest backend/tests -q`

Expected: both commands exit 0.

- [ ] **Step 2: Run Web tests and production build**

Run: `npm test --prefix web`

Run: `npm run build --prefix web`

Expected: both commands exit 0.

- [ ] **Step 3: Run Unity tests and check console**

Run EditMode tests via Unity MCP, wait for completion, and read error console.

Expected: all digital-human tests PASS and zero compiler/runtime errors.

- [ ] **Step 4: Run local browser acceptance check**

Start the backend and Vite dev server, open `/counselor`, log in, ask one short campus question, and verify:

1. DeepSeek answer streams as text.
2. TTS begins after the final answer and uses the “冰糖” voice.
3. Rusk mouth follows speech amplitude.
4. Head/Neck remain subtle at idle and add small speaking nods.
5. Stop, mute, replay, session change, and a second question never overlap audio.
6. Disabling or breaking TTS leaves the text response usable.

- [ ] **Step 5: Perform final secret and scope checks**

Run: `git diff --check`

Run: `git status --short`

Run: `git diff | Select-String -Pattern 'sk-[A-Za-z0-9]{16,}'`

Run a second recursive scan over changed source files and the WebGL output. Expected: no real key matches and no unrelated dirty files are staged.

- [ ] **Step 6: Document runtime configuration and commit it**

Add the exact DeepSeek and MiMo environment variable names, the WebGL output directory, and the local build/start order. Use placeholder values only.

```powershell
git add backend/README.md web/README.md
git commit -m "docs: document digital human runtime setup"
```

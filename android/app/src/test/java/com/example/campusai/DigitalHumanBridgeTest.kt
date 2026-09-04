package com.example.campusai

import com.example.campusai.ui.screens.counselor.DigitalHumanBridge
import com.example.campusai.ui.screens.counselor.DigitalHumanLoadEvent
import com.example.campusai.ui.screens.counselor.DigitalHumanRenderMode
import com.example.campusai.ui.screens.counselor.DigitalHumanStageLoadState
import com.example.campusai.ui.screens.counselor.nextDigitalHumanStageLoadState
import com.example.campusai.ui.screens.counselor.selectDigitalHumanRenderMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DigitalHumanBridgeTest {
    @Test
    fun `main document failure switches the stage to the bundled avatar`() {
        assertEquals(
            DigitalHumanStageLoadState.FALLBACK,
            nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.MAIN_FRAME_FAILED),
        )
    }

    @Test
    fun `webview renderer failure switches the stage to the bundled avatar`() {
        assertEquals(
            DigitalHumanStageLoadState.FALLBACK,
            nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.RENDERER_GONE),
        )
    }

    @Test
    fun `a trusted completed document makes the web stage ready`() {
        assertEquals(
            DigitalHumanStageLoadState.READY,
            nextDigitalHumanStageLoadState(DigitalHumanLoadEvent.TRUSTED_PAGE_FINISHED),
        )
    }

    @Test
    fun `x86 emulators use the lightweight native avatar and audio bridge`() {
        assertEquals(
            DigitalHumanRenderMode.NATIVE_COMPAT,
            selectDigitalHumanRenderMode(
                fingerprint = "google/sdk_gphone64_x86_64/generic",
                model = "sdk_gphone64_x86_64",
                supportedAbis = listOf("x86_64"),
                lowRamDevice = false,
            ),
        )
    }

    @Test
    fun `low ram arm phones avoid the large Unity WebGL runtime`() {
        assertEquals(
            DigitalHumanRenderMode.NATIVE_COMPAT,
            selectDigitalHumanRenderMode(
                fingerprint = "vendor/device/release",
                model = "Entry Android",
                supportedAbis = listOf("arm64-v8a", "armeabi-v7a"),
                lowRamDevice = true,
            ),
        )
    }

    @Test
    fun `arm64 physical phones keep the live digital human`() {
        assertEquals(
            DigitalHumanRenderMode.LIVE_WEBGL,
            selectDigitalHumanRenderMode(
                fingerprint = "google/komodo/komodo:16/BP2A",
                model = "Pixel 9 Pro XL",
                supportedAbis = listOf("arm64-v8a", "armeabi-v7a"),
                lowRamDevice = false,
            ),
        )
    }

    @Test
    fun `stage url uses API origin instead of embedding credentials`() {
        assertEquals(
            "http://10.0.2.2:8000/digital-human/mobile.html?embed=1",
            DigitalHumanBridge.stageUrl("http://10.0.2.2:8000/api/v1/"),
        )
    }

    @Test
    fun `compatibility stage skips the Unity payload but keeps the speech runtime`() {
        assertEquals(
            "http://10.0.2.2:8000/digital-human/mobile.html?embed=1&fallback=1",
            DigitalHumanBridge.stageUrl("http://10.0.2.2:8000/api/v1/", forceFallback = true),
        )
    }

    @Test
    fun `stage url forwards the app reduced motion preference`() {
        assertEquals(
            "http://10.0.2.2:8000/digital-human/mobile.html?embed=1&fallback=1&reduceMotion=1",
            DigitalHumanBridge.stageUrl(
                "http://10.0.2.2:8000/api/v1/",
                forceFallback = true,
                reduceMotion = true,
            ),
        )
    }

    @Test
    fun `stage scripts only run on the expected digital human document`() {
        val expected = "https://campus.example/digital-human/mobile.html?embed=1&fallback=1"

        assertTrue(DigitalHumanBridge.isTrustedStageUrl(expected, expected))
        assertTrue(DigitalHumanBridge.isTrustedStageUrl(expected, "$expected#avatar"))
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://evil.example/digital-human/mobile.html?embed=1&fallback=1",
            ),
        )
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://campus.example/other.html?embed=1&fallback=1",
            ),
        )
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://campus.example/digital-human/mobile.html?embed=1",
            ),
        )
    }

    @Test
    fun `configure script safely quotes token and API URL`() {
        assertEquals(
            "window.CampusMateDigitalHuman.configure({apiBaseUrl:\"https://campus.example/api/v1\",accessToken:\"a\\\"b\"});",
            DigitalHumanBridge.configureScript("https://campus.example/api/v1", "a\"b"),
        )
    }

    @Test
    fun `speech script preserves newlines and quotes`() {
        assertEquals(
            "window.CampusMateDigitalHuman.speak(\"第一行\\n\\\"第二行\\\"\");",
            DigitalHumanBridge.speakScript("第一行\n\"第二行\""),
        )
    }

    @Test
    fun `native playback controls call the embedded runtime API`() {
        assertEquals(
            "window.CampusMateDigitalHuman.toggleMuted();",
            DigitalHumanBridge.commandScript(com.example.campusai.ui.screens.counselor.DigitalHumanCommand.TOGGLE_MUTE),
        )
        assertEquals(
            "window.CampusMateDigitalHuman.togglePaused();",
            DigitalHumanBridge.commandScript(com.example.campusai.ui.screens.counselor.DigitalHumanCommand.TOGGLE_PAUSE),
        )
        assertEquals(
            "window.CampusMateDigitalHuman.replay();",
            DigitalHumanBridge.commandScript(com.example.campusai.ui.screens.counselor.DigitalHumanCommand.REPLAY),
        )
    }
}

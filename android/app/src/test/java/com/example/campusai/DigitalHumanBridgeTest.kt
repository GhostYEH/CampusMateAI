package com.example.campusai

import com.example.campusai.ui.screens.counselor.DigitalHumanBridge
import com.example.campusai.ui.screens.counselor.DigitalHumanRenderMode
import com.example.campusai.ui.screens.counselor.selectDigitalHumanRenderMode
import com.example.campusai.ui.screens.counselor.shouldCreateEmbeddedDigitalHuman
import org.junit.Assert.assertEquals
import org.junit.Test

class DigitalHumanBridgeTest {
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
    fun `native compatibility mode never creates the embedded WebView runtime`() {
        assertEquals(false, shouldCreateEmbeddedDigitalHuman(DigitalHumanRenderMode.NATIVE_COMPAT))
        assertEquals(true, shouldCreateEmbeddedDigitalHuman(DigitalHumanRenderMode.LIVE_WEBGL))
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

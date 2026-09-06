package com.example.campusai

import com.example.campusai.ui.screens.counselor.DigitalHumanBridge
import com.example.campusai.ui.screens.counselor.DigitalHumanLoadEvent
import com.example.campusai.ui.screens.counselor.DigitalHumanStageLoadState
import com.example.campusai.ui.screens.counselor.nextDigitalHumanStageLoadState
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
    fun `stage url uses the APK bundled Rusk scene`() {
        assertEquals(
            "https://appassets.androidplatform.net/assets/digital-human/index.html",
            DigitalHumanBridge.stageUrl("http://10.0.2.2:8000/api/v1/"),
        )
    }

    @Test
    fun `stage url forwards the app reduced motion preference`() {
        assertEquals(
            "https://appassets.androidplatform.net/assets/digital-human/index.html?reduceMotion=1",
            DigitalHumanBridge.stageUrl(
                "http://10.0.2.2:8000/api/v1/",
                reduceMotion = true,
            ),
        )
    }

    @Test
    fun `stage scripts only run on the expected digital human document`() {
        val expected = "https://campus.example/digital-human/"

        assertTrue(DigitalHumanBridge.isTrustedStageUrl(expected, expected))
        assertTrue(DigitalHumanBridge.isTrustedStageUrl(expected, "$expected#avatar"))
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://evil.example/digital-human/",
            ),
        )
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://campus.example/other/",
            ),
        )
        assertFalse(
            DigitalHumanBridge.isTrustedStageUrl(
                expected,
                "https://campus.example/digital-human/?fallback=1",
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
    fun `presentation script enlarges Rusk and respects reduced motion`() {
        assertEquals(
            "window.CampusMateDigitalHuman.setPresentation({zoom:1.18,idleMotion:true});",
            DigitalHumanBridge.presentationScript(reduceMotion = false),
        )
        assertEquals(
            "window.CampusMateDigitalHuman.setPresentation({zoom:1.18,idleMotion:false});",
            DigitalHumanBridge.presentationScript(reduceMotion = true),
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

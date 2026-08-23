package com.example.campusai

import com.example.campusai.ui.screens.counselor.DigitalHumanBridge
import org.junit.Assert.assertEquals
import org.junit.Test

class DigitalHumanBridgeTest {
    @Test
    fun `stage url uses API origin instead of embedding credentials`() {
        assertEquals(
            "http://10.0.2.2:8000/digital-human/mobile.html",
            DigitalHumanBridge.stageUrl("http://10.0.2.2:8000/api/v1/"),
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
}

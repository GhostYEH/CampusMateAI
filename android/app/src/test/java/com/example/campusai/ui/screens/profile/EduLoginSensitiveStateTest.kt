package com.example.campusai.ui.screens.profile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class EduLoginSensitiveStateTest {
    @Test
    fun captchaChallengeIsCapturedInTheSameStateThatLifecycleEventsClear() {
        val captured = captureEduLoginChallenge(
            EduLoginSensitiveState(username = "student-1", password = "secret"),
            captcha = "1234",
            preLoginToken = "pre-login-token",
        )

        assertEquals("1234", captured.captcha)
        assertEquals("pre-login-token", captured.preLoginToken)
        val cleared = reduceEduLoginSensitiveState(captured, EduLoginSensitiveEvent.DIRECT_CONNECTED)
        assertEquals("", cleared.password)
        assertEquals("", cleared.captcha)
        assertNull(cleared.preLoginToken)
    }

    @Test
    fun everySensitiveLifecycleExitClearsSecretsButKeepsUsername() {
        for (event in EduLoginSensitiveEvent.entries) {
            val result = reduceEduLoginSensitiveState(
                EduLoginSensitiveState(
                    username = "student-1",
                    password = "secret",
                    captcha = "1234",
                    preLoginToken = "pre-login-token",
                ),
                event,
            )

            assertEquals("event=$event", "student-1", result.username)
            assertEquals("event=$event", "", result.password)
            assertEquals("event=$event", "", result.captcha)
            assertNull("event=$event", result.preLoginToken)
        }
    }
}

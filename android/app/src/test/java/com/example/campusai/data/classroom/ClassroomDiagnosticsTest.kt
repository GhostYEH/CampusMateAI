package com.example.campusai.data.classroom

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.shadows.ShadowLog

@RunWith(RobolectricTestRunner::class)
class ClassroomDiagnosticsTest {
    @Test
    fun `only whitelisted diagnostic fields and error type are logged`() {
        ShadowLog.clear()
        ClassroomDiagnostics.warn(
            "classroom_test_event",
            IllegalStateException("secret token"),
            "stage" to "submit",
            "status" to "Unknown",
            "uid" to "user-42",
            "url" to "https://example.com/classroom?token=secret",
        )

        val entry = ShadowLog.getLogsForTag("CampusClassroom").single()
        assertTrue(entry.msg.contains("classroom_test_event"))
        assertTrue(entry.msg.contains("stage=submit"))
        assertTrue(entry.msg.contains("status=Unknown"))
        assertTrue(entry.msg.contains("error=IllegalStateException"))
        assertFalse(entry.msg.contains("secret token"))
        assertFalse(entry.msg.contains("uid"))
        assertFalse(entry.msg.contains("url"))
    }

    @Test
    fun `unsafe field values are dropped`() {
        ShadowLog.clear()
        ClassroomDiagnostics.warn(
            "classroom_test_event",
            null,
            "status" to "token=secret",
            "component" to "video",
        )

        val entry = ShadowLog.getLogsForTag("CampusClassroom").single()
        assertFalse(entry.msg.contains("token=secret"))
        assertTrue(entry.msg.contains("component=video"))
    }
}

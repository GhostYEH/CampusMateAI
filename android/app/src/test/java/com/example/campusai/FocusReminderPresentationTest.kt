package com.example.campusai

import com.example.campusai.data.model.FocusSessionMode
import com.example.campusai.ui.screens.focus.presentFocusReminder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FocusReminderPresentationTest {
    @Test
    fun presentsReminderOnlyForEnabledSmartGuard() {
        val reminder = "检测到持续手机交互，请确认它是否与当前学习任务有关。"

        assertEquals(reminder, presentFocusReminder(FocusSessionMode.SMART_GUARD, true, reminder))
        assertNull(presentFocusReminder(FocusSessionMode.SMART_GUARD, false, reminder))
        assertNull(presentFocusReminder(FocusSessionMode.QUIET, true, reminder))
        assertNull(presentFocusReminder(FocusSessionMode.SMART_GUARD, true, ""))
    }
}

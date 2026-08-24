package com.example.campusai.data.expression

import org.junit.Assert.assertEquals
import org.junit.Test

class FocusReminderStateTest {

    @Test
    fun clearingBehaviorReminderDoesNotClearExpressionReminder() {
        val state = FocusReminderState()
        state.setExpression("表情提醒")
        state.setBehavior("行为提醒")

        state.clearBehavior()

        assertEquals("表情提醒", state.message())
    }

    @Test
    fun behaviorReminderHasPriorityWhileBothSignalsAreActive() {
        val state = FocusReminderState()
        state.setExpression("表情提醒")
        state.setBehavior("行为提醒")

        assertEquals("行为提醒", state.message())
    }

    @Test
    fun clearingExpressionReminderDoesNotClearBehaviorReminder() {
        val state = FocusReminderState()
        state.setExpression("表情提醒")
        state.setBehavior("行为提醒")

        state.clearExpression()

        assertEquals("行为提醒", state.message())
    }
}


package com.example.campusai.data.expression

/** Keeps independent reminder producers from accidentally clearing each other. */
class FocusReminderState {
    private var expressionReminder: String? = null
    private var behaviorReminder: String? = null

    fun setExpression(message: String) { expressionReminder = message }
    fun setBehavior(message: String) { behaviorReminder = message }
    fun clearExpression() { expressionReminder = null }
    fun clearBehavior() { behaviorReminder = null }
    fun clearAll() {
        expressionReminder = null
        behaviorReminder = null
    }

    fun message(): String? = behaviorReminder ?: expressionReminder
}


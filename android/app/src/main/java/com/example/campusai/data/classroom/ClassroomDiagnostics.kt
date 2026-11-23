package com.example.campusai.data.classroom

import android.util.Log

/**
 * 课堂模块的低噪声诊断出口。
 *
 * 只允许固定事件名和白名单字段，字段值限制为字母、数字、下划线和少量结构符号，
 * 且最多 32 个字符。异常只记录类型，不记录 message、堆栈、URL、令牌、UID、
 * 消息正文、答案或课件原文。
 */
object ClassroomDiagnostics {
    private const val TAG = "CampusClassroom"
    private const val MAX_VALUE_LENGTH = 32
    private val allowedKeys = setOf(
        "stage",
        "status",
        "component",
        "attempts",
        "code",
        "label",
        "phase",
        "service",
    )
    private val safeValue = Regex("[A-Za-z0-9_.:+-]+")

    fun warn(event: String, error: Throwable? = null, vararg fields: Pair<String, Any?>) {
        val rendered = fields.mapNotNull { (key, value) ->
            if (key !in allowedKeys) return@mapNotNull null
            val text = value?.toString()?.take(MAX_VALUE_LENGTH) ?: return@mapNotNull null
            if (!safeValue.matches(text)) return@mapNotNull null
            "$key=$text"
        }.joinToString(" ")
        val errorType = error?.javaClass?.simpleName?.takeIf { safeValue.matches(it) }
        val suffix = buildString {
            if (errorType != null) append(" error=$errorType")
            if (rendered.isNotEmpty()) append(' ').append(rendered)
        }
        Log.w(TAG, if (suffix.isEmpty()) event else "$event$suffix")
    }
}

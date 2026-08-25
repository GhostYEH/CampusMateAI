package com.example.campusai.data.expression

import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.model.ExpressionResult

/** Precision-first policy for using a local FER result in CPM conversations. */
object CounselorExpressionPolicy {
    private const val MAX_AGE_MS = 5_000L
    private const val FUTURE_TOLERANCE_MS = 2_000L
    private val thresholds = mapOf(
        ExpressionLabel.NEUTRAL to .83,
        ExpressionLabel.HAPPY to .30,
        ExpressionLabel.SAD to .68,
        ExpressionLabel.ANGRY to .81,
        ExpressionLabel.FEAR to .80,
        ExpressionLabel.SURPRISE to .78,
        ExpressionLabel.DISGUST to .91,
    )

    fun isUsable(result: ExpressionResult, nowMs: Long = System.currentTimeMillis()): Boolean {
        val threshold = thresholds[result.label] ?: return false
        val ageMs = nowMs - result.timestamp
        return result.isStable &&
            result.confidence >= threshold &&
            ageMs in -FUTURE_TOLERANCE_MS..MAX_AGE_MS
    }

    fun usableOrNull(
        result: ExpressionResult,
        nowMs: Long = System.currentTimeMillis(),
    ): ExpressionResult? = result.takeIf { isUsable(it, nowMs) }

    fun greeting(
        result: ExpressionResult,
        nowMs: Long = System.currentTimeMillis(),
    ): String? {
        if (!isUsable(result, nowMs)) return null
        return when (result.label) {
            ExpressionLabel.SAD ->
                "看起来你现在可能有些难过。别难过，也别一个人扛着，我在这里陪你；想聊聊，或者一起解决一件具体的事都可以。"
            ExpressionLabel.ANGRY ->
                "看起来你现在可能有些烦躁，我们先慢一点。我会认真听你说，也可以陪你把眼前的问题一步步理清。"
            ExpressionLabel.FEAR ->
                "看起来你现在可能有些紧张，先别急，我们可以从最容易处理的一步开始。"
            ExpressionLabel.DISGUST ->
                "看起来你现在可能有些不舒服，我们可以换个轻松一点的方式慢慢聊。"
            ExpressionLabel.HAPPY ->
                "看到你状态不错真好！我是 AI 校园助手小灵，今天想聊聊校园生活，还是一起解决一个具体问题？"
            ExpressionLabel.SURPRISE ->
                "看起来刚才可能有件事让你有些意外。愿意的话可以告诉我，我陪你一起理清。"
            ExpressionLabel.NEUTRAL ->
                "你好，我是 AI 校园助手小灵。课程流程、奖助政策、校园服务，或者最近想聊的事，都可以告诉我。"
            else -> null
        }
    }
}

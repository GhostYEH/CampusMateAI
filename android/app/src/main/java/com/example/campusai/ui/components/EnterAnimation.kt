package com.example.campusai.ui.components

import androidx.compose.animation.core.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer

/**
 * 增强版入场动画：淡入 + 上滑 + 轻微放大，营造层次丰富的渐进感。
 * [delayMs] 交错延迟，[scaleFrom] 起始缩放（默认 0.94），[slideDistance] 上滑距离（dp）。
 */
@Composable
fun Modifier.enterAnimation(
    delayMs: Int = 0,
    scaleFrom: Float = 0.94f,
    slideDistance: Float = 18f,
    enabled: Boolean = true,
): Modifier {
    if (!enabled) return this
    var hasFinished by remember { mutableStateOf(false) }
    val progress by animateFloatAsState(
        targetValue = if (hasFinished) 1f else 0f,
        animationSpec = tween(
            durationMillis = 700,
            delayMillis = delayMs,
            easing = CubicBezierEasing(0.22f, 0.82f, 0.2f, 1f),
        ),
        label = "enter-progress",
    )
    LaunchedEffect(Unit) { hasFinished = true }
    return this.graphicsLayer {
        alpha = progress
        translationY = slideDistance * (1f - progress)
        scaleX = 1f - (1f - scaleFrom) * (1f - progress)
        scaleY = 1f - (1f - scaleFrom) * (1f - progress)
    }
}

/**
 * 从侧面滑入动画 — 用于列表项、消息气泡等。
 * [fromLeft] true=左侧滑入，false=右侧滑入。
 */
@Composable
fun Modifier.slideInAnimation(
    delayMs: Int = 0,
    fromLeft: Boolean = true,
    enabled: Boolean = true,
): Modifier {
    if (!enabled) return this
    var hasFinished by remember { mutableStateOf(false) }
    val progress by animateFloatAsState(
        targetValue = if (hasFinished) 1f else 0f,
        animationSpec = tween(
            durationMillis = 500,
            delayMillis = delayMs,
            easing = CubicBezierEasing(0.18f, 0.8f, 0.24f, 1f),
        ),
        label = "slide-progress",
    )
    LaunchedEffect(Unit) { hasFinished = true }
    val offset = 60f * (1f - progress) * if (fromLeft) -1f else 1f
    return this.graphicsLayer {
        alpha = progress
        translationX = offset
        translationY = 8f * (1f - progress)
    }
}

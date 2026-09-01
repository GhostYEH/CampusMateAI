package com.example.campusai.ui.components

import androidx.compose.animation.core.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.LocalReduceMotion

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
    if (!enabled || LocalReduceMotion.current) return this
    var hasFinished by remember { mutableStateOf(false) }
    val slideDistancePx = with(LocalDensity.current) { slideDistance.dp.toPx() }
    val progress by animateFloatAsState(
        targetValue = if (hasFinished) 1f else 0f,
        animationSpec = tween(
            durationMillis = CampusMotion.enterDuration,
            delayMillis = delayMs.coerceIn(0, CampusMotion.maxStaggerDelay),
            easing = CampusMotion.enterEasing,
        ),
        label = "enter-progress",
    )
    LaunchedEffect(Unit) { hasFinished = true }
    return this.graphicsLayer {
        alpha = progress
        translationY = slideDistancePx * (1f - progress)
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
    if (!enabled || LocalReduceMotion.current) return this
    var hasFinished by remember { mutableStateOf(false) }
    val slideDistancePx = with(LocalDensity.current) { 44.dp.toPx() }
    val liftDistancePx = with(LocalDensity.current) { 6.dp.toPx() }
    val progress by animateFloatAsState(
        targetValue = if (hasFinished) 1f else 0f,
        animationSpec = tween(
            durationMillis = 440,
            delayMillis = delayMs.coerceIn(0, CampusMotion.maxStaggerDelay),
            easing = CampusMotion.settleEasing,
        ),
        label = "slide-progress",
    )
    LaunchedEffect(Unit) { hasFinished = true }
    val offset = slideDistancePx * (1f - progress) * if (fromLeft) -1f else 1f
    return this.graphicsLayer {
        alpha = progress
        translationX = offset
        translationY = liftDistancePx * (1f - progress)
        scaleX = 0.985f + 0.015f * progress
        scaleY = 0.985f + 0.015f * progress
    }
}

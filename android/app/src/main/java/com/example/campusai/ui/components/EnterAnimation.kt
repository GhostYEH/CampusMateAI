package com.example.campusai.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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

    var animationStarted by remember { mutableStateOf(false) }
    val slideDistancePx = with(LocalDensity.current) { slideDistance.dp.toPx() }
    val progress by animateFloatAsState(
        targetValue = if (animationStarted) 1f else 0f,
        animationSpec = tween(
            durationMillis = CampusMotion.enterDuration,
            delayMillis = delayMs.coerceIn(0, CampusMotion.maxStaggerDelay),
            easing = CampusMotion.enterEasing,
        ),
        label = "enter-progress",
    )
    LaunchedEffect(Unit) { animationStarted = true }

    return this.graphicsLayer {
        val remainingProgress = 1f - progress
        alpha = progress
        translationY = slideDistancePx * remainingProgress
        scaleX = 1f - (1f - scaleFrom) * remainingProgress
        scaleY = 1f - (1f - scaleFrom) * remainingProgress
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

    var animationStarted by remember { mutableStateOf(false) }
    val density = LocalDensity.current
    val slideDistancePx = with(density) { 44.dp.toPx() }
    val liftDistancePx = with(density) { 6.dp.toPx() }
    val progress by animateFloatAsState(
        targetValue = if (animationStarted) 1f else 0f,
        animationSpec = tween(
            durationMillis = 440,
            delayMillis = delayMs.coerceIn(0, CampusMotion.maxStaggerDelay),
            easing = CampusMotion.settleEasing,
        ),
        label = "slide-progress",
    )
    LaunchedEffect(Unit) { animationStarted = true }

    val direction = if (fromLeft) -1f else 1f
    return this.graphicsLayer {
        val remainingProgress = 1f - progress
        alpha = progress
        translationX = slideDistancePx * remainingProgress * direction
        translationY = liftDistancePx * remainingProgress
        scaleX = 0.985f + 0.015f * progress
        scaleY = 0.985f + 0.015f * progress
    }
}

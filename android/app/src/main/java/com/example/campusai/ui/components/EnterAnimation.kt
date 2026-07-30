package com.example.campusai.ui.components

import androidx.compose.animation.core.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer

@Composable
fun Modifier.enterAnimation(
    delayMs: Int = 0,
    enabled: Boolean = true
): Modifier {
    if (!enabled) return this
    var hasFinished by remember { mutableStateOf(false) }
    val progress by animateFloatAsState(
        targetValue = if (hasFinished) 1f else 0f,
        animationSpec = tween(
            durationMillis = 650,
            delayMillis = delayMs,
            easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f)
        )
    )
    LaunchedEffect(Unit) { hasFinished = true }
    return this.graphicsLayer {
        alpha = progress
        translationY = 16f * (1f - progress)
    }
}

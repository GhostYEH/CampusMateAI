package com.example.campusai.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.spring
import androidx.compose.foundation.clickable
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.Role
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Primary

/**
 * CampusMate 的平台无关点击反馈：没有 Material 水波纹，只使用轻微压缩。
 * 保留语义与可访问性，不依赖 Android 原生视觉效果。
 */
@Composable
fun Modifier.campusClickable(
    enabled: Boolean = true,
    role: Role? = Role.Button,
    onClick: () -> Unit,
): Modifier {
    val source = remember { MutableInteractionSource() }
    val pressed by source.collectIsPressedAsState()
    val reduceMotion = LocalReduceMotion.current
    val primaryColor = Primary
    val pressGlow = remember { Animatable(0f) }
    val scale by animateFloatAsState(
        targetValue = if (pressed && enabled && !reduceMotion) 0.975f else 1f,
        animationSpec = spring(stiffness = 760f, dampingRatio = .88f),
        label = "campus-press",
    )
    LaunchedEffect(pressed, enabled, reduceMotion) {
        if (!enabled || reduceMotion) {
            pressGlow.snapTo(0f)
        } else if (pressed) {
            pressGlow.animateTo(
                targetValue = 1f,
                animationSpec = androidx.compose.animation.core.tween(
                    CampusMotion.pressDuration,
                    easing = CampusMotion.settleEasing,
                ),
            )
        } else {
            pressGlow.animateTo(
                targetValue = 0f,
                animationSpec = androidx.compose.animation.core.tween(
                    CampusMotion.releaseDuration,
                    easing = CampusMotion.settleEasing,
                ),
            )
        }
    }
    return graphicsLayer {
        scaleX = scale
        scaleY = scale
        alpha = if (enabled) 1f else .52f
    }.drawBehind {
        val glow = pressGlow.value
        if (glow > 0f) {
            drawRoundRect(
                brush = Brush.radialGradient(
                    colors = listOf(primaryColor.copy(alpha = 0.14f * glow), Color.Transparent),
                    center = Offset(size.width / 2f, size.height / 2f),
                    radius = size.maxDimension * .78f,
                ),
                cornerRadius = CornerRadius(size.minDimension * .22f),
            )
        }
    }.clickable(
        interactionSource = source,
        indication = null,
        enabled = enabled,
        role = role,
        onClick = onClick,
    )
}

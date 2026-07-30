package com.example.campusai.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.Role

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
    val scale by animateFloatAsState(
        targetValue = if (pressed && enabled) 0.975f else 1f,
        animationSpec = spring(stiffness = 700f, dampingRatio = .9f),
        label = "campus-press",
    )
    return graphicsLayer {
        scaleX = scale
        scaleY = scale
        alpha = if (enabled) 1f else .52f
    }.clickable(
        interactionSource = source,
        indication = null,
        enabled = enabled,
        role = role,
        onClick = onClick,
    )
}

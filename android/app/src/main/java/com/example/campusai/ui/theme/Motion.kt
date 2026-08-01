package com.example.campusai.ui.theme

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Indication
import androidx.compose.foundation.IndicationInstance
import androidx.compose.foundation.LocalIndication
import androidx.compose.foundation.interaction.InteractionSource
import androidx.compose.foundation.interaction.PressInteraction
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.remember
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.ContentDrawScope
import kotlinx.coroutines.flow.collect

/**
 * A single motion switch shared by page transitions, components and custom
 * press feedback. The setting is app-owned rather than tied to the device
 * animator scale so the demo mode remains deterministic.
 */
val LocalReduceMotion = staticCompositionLocalOf { false }

object CampusMotion {
    const val enterDuration = 560
    const val routeEnterDuration = 360
    const val routeExitDuration = 260
    const val pressDuration = 130
    const val releaseDuration = 260

    val enterEasing = CubicBezierEasing(0.22f, 0.86f, 0.2f, 1f)
    val settleEasing = CubicBezierEasing(0.18f, 0.8f, 0.24f, 1f)
    val routeEasing = FastOutSlowInEasing
}

/**
 * Replaces the stock ripple with a small, intentional focus/press wash.
 * It is deliberately low-contrast so it supports the tap without becoming a
 * second visual layer, and it follows the same motion-reduction setting.
 */
@OptIn(ExperimentalFoundationApi::class)
@Stable
private class CampusIndication(
    private val highlight: Color,
    private val reduceMotion: Boolean,
) : Indication {
    @Composable
    override fun rememberUpdatedInstance(interactionSource: InteractionSource): IndicationInstance {
        val instance = remember(interactionSource, highlight, reduceMotion) {
            CampusIndicationInstance(highlight, reduceMotion)
        }
        LaunchedEffect(interactionSource, instance) {
            interactionSource.interactions.collect { interaction ->
                when (interaction) {
                    is PressInteraction.Press -> instance.onPress()
                    is PressInteraction.Release,
                    is PressInteraction.Cancel -> instance.onRelease()
                }
            }
        }
        return instance
    }
}

@OptIn(ExperimentalFoundationApi::class)
private class CampusIndicationInstance(
    private val highlight: Color,
    private val reduceMotion: Boolean,
) : IndicationInstance {
    private val progress = Animatable(0f)

    suspend fun onPress() {
        if (reduceMotion) return
        progress.snapTo(0.12f)
        progress.animateTo(
            targetValue = 1f,
            animationSpec = tween(CampusMotion.pressDuration, easing = CampusMotion.settleEasing),
        )
    }

    suspend fun onRelease() {
        if (reduceMotion) return
        progress.animateTo(
            targetValue = 0f,
            animationSpec = tween(CampusMotion.releaseDuration, easing = CampusMotion.settleEasing),
        )
    }

    override fun ContentDrawScope.drawIndication() {
        drawContent()
        val alpha = progress.value * 0.1f
        if (alpha <= 0f) return
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(highlight.copy(alpha = alpha), Color.Transparent),
                center = Offset(size.width / 2f, size.height / 2f),
                radius = size.maxDimension * 0.82f,
            ),
            radius = size.maxDimension * 0.82f,
            center = Offset(size.width / 2f, size.height / 2f),
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun rememberCampusIndication(highlight: Color): Indication {
    val reduceMotion = LocalReduceMotion.current
    return remember(highlight, reduceMotion) {
        CampusIndication(highlight, reduceMotion)
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
internal fun ProvideCampusIndication(content: @Composable () -> Unit) {
    androidx.compose.runtime.CompositionLocalProvider(
        LocalIndication provides rememberCampusIndication(Primary),
        content = content,
    )
}

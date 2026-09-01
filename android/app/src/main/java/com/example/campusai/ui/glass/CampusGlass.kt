package com.example.campusai.ui.glass

import android.os.Build
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.kashif_e.backdrop.Backdrop
import com.kashif_e.backdrop.backdrops.layerBackdrop
import com.kashif_e.backdrop.backdrops.rememberLayerBackdrop
import com.kashif_e.backdrop.drawBackdrop
import com.kashif_e.backdrop.effects.blur
import com.kashif_e.backdrop.effects.lens
import com.kashif_e.backdrop.effects.vibrancy
import com.kashif_e.backdrop.highlight.Highlight
import com.kashif_e.backdrop.shadow.Shadow

val LocalCampusBackdrop = staticCompositionLocalOf<Backdrop?> { null }

private fun DrawScope.drawAmbientGlow(
    color: Color,
    center: Offset,
    radius: Float,
) {
    drawCircle(
        brush = Brush.radialGradient(
            colors = listOf(color, Color.Transparent),
            center = center,
            radius = radius,
        ),
        radius = radius,
        center = center,
    )
}

@Composable
private fun defaultGlassTint(role: CampusGlassRole): Color = when (role) {
    CampusGlassRole.NAVIGATION -> Surface.copy(alpha = .46f)
    CampusGlassRole.PANEL -> Surface.copy(alpha = .54f)
    CampusGlassRole.CONTROL -> PrimarySoft.copy(alpha = .48f)
    CampusGlassRole.DENSE -> Surface.copy(alpha = .68f)
}

@Composable
fun CampusGlassScene(
    darkMode: Boolean,
    modifier: Modifier = Modifier,
    background: (@Composable BoxScope.() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    val backdrop = rememberLayerBackdrop()
    val primary = Primary
    val ambientColors = if (darkMode) {
        listOf(Color(0xFF07161D), Color(0xFF102B37), Color(0xFF183047))
    } else {
        listOf(Color(0xFFF4FAFC), Color(0xFFE4F3F7), Color(0xFFE9EEF9))
    }
    Box(modifier.fillMaxSize()) {
        val backgroundModifier = if (background == null) {
            Modifier
                .fillMaxSize()
                .layerBackdrop(backdrop)
                .background(Brush.linearGradient(ambientColors))
                .drawBehind {
                    drawAmbientGlow(
                        color = primary.copy(alpha = if (darkMode) .24f else .18f),
                        center = Offset(size.width * .86f, size.height * .12f),
                        radius = size.minDimension * .78f,
                    )
                    drawAmbientGlow(
                        color = Color(0xFF8E7CFF).copy(alpha = .13f),
                        center = Offset(size.width * .08f, size.height * .74f),
                        radius = size.minDimension * .62f,
                    )
                }
        } else {
            Modifier
                .fillMaxSize()
                .layerBackdrop(backdrop)
        }
        Box(backgroundModifier) {
            background?.invoke(this)
        }
        CompositionLocalProvider(LocalCampusBackdrop provides backdrop) {
            content()
        }
    }
}

@Composable
fun Modifier.campusGlass(
    shape: Shape,
    role: CampusGlassRole = CampusGlassRole.PANEL,
    tint: Color = Color.Unspecified,
    interactionProgress: Float = 0f,
    glowColor: Color = Primary,
): Modifier {
    val backdrop = LocalCampusBackdrop.current
    val reduceMotion = LocalReduceMotion.current
    val profile = campusGlassProfile(Build.VERSION.SDK_INT, reduceMotion)
    val roleEffects = profile.effectsFor(role)
    val resolvedTint = if (tint == Color.Unspecified) defaultGlassTint(role) else tint
    val glowProgress = if (reduceMotion) 0f else interactionProgress.coerceIn(0f, 1f)
    val usesVibrancy = role == CampusGlassRole.NAVIGATION ||
        role == CampusGlassRole.PANEL ||
        glowProgress > 0f
    val usesLens = profile.lensEnabled &&
        (roleEffects.lensAtRest || roleEffects.lensOnPress && glowProgress > 0f)

    if (backdrop == null || profile.quality == CampusGlassQuality.PAINTED) {
        return this
            .clip(shape)
            .background(resolvedTint)
            .border(1.dp, Color.White.copy(alpha = .38f), shape)
            .drawBehind {
                if (glowProgress > 0f || roleEffects.glowAtRest) {
                    val center = Offset(size.width * .76f, size.height * .18f)
                    val radius = size.maxDimension * .72f
                    drawCircle(
                        brush = Brush.radialGradient(
                            listOf(
                                glowColor.copy(alpha = .16f + glowProgress * .18f),
                                Color.Transparent,
                            ),
                            center = center,
                            radius = radius,
                        ),
                        radius = radius,
                        center = center,
                    )
                }
            }
    }

    return this.drawBackdrop(
        backdrop = backdrop,
        shape = { shape },
        effects = {
            if (usesVibrancy) vibrancy()
            if (roleEffects.blurRadiusDp > 0f) blur(roleEffects.blurRadiusDp.dp.toPx())
            if (usesLens) {
                val progress = if (roleEffects.lensAtRest) 1f else glowProgress
                lens(12.dp.toPx() * progress, 22.dp.toPx() * progress)
            }
        },
        highlight = {
            Highlight.Ambient.copy(alpha = .58f + glowProgress * .32f)
        },
        shadow = {
            Shadow(
                radius = if (role == CampusGlassRole.NAVIGATION) 14.dp else 7.dp,
                color = glowColor.copy(alpha = .08f + glowProgress * .12f),
            )
        },
        onDrawSurface = {
            drawRect(lerp(resolvedTint, glowColor.copy(alpha = .18f), glowProgress * .22f))
        },
    )
}

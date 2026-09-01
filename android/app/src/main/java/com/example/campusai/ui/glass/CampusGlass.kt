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
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.theme.Background
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

@Composable
fun CampusGlassScene(
    darkMode: Boolean,
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit,
) {
    val backdrop = rememberLayerBackdrop()
    val primary = Primary
    val ambient = if (darkMode) {
        listOf(Color(0xFF07161D), Color(0xFF102B37), Color(0xFF183047))
    } else {
        listOf(Color(0xFFF4FAFC), Color(0xFFE4F3F7), Color(0xFFE9EEF9))
    }
    Box(modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxSize()
                .layerBackdrop(backdrop)
                .background(
                    Brush.linearGradient(
                        colors = ambient,
                    ),
                )
                .drawBehind {
                    drawCircle(
                        brush = Brush.radialGradient(
                            listOf(primary.copy(alpha = if (darkMode) .24f else .18f), Color.Transparent),
                            center = Offset(size.width * .86f, size.height * .12f),
                            radius = size.minDimension * .78f,
                        ),
                        radius = size.minDimension * .78f,
                        center = Offset(size.width * .86f, size.height * .12f),
                    )
                    drawCircle(
                        brush = Brush.radialGradient(
                            listOf(Color(0xFF8E7CFF).copy(alpha = .13f), Color.Transparent),
                            center = Offset(size.width * .08f, size.height * .74f),
                            radius = size.minDimension * .62f,
                        ),
                        radius = size.minDimension * .62f,
                        center = Offset(size.width * .08f, size.height * .74f),
                    )
                },
        )
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
    val effects = profile.effectsFor(role)
    val resolvedTint = if (tint != Color.Unspecified) tint else when (role) {
        CampusGlassRole.NAVIGATION -> Surface.copy(alpha = .46f)
        CampusGlassRole.PANEL -> Surface.copy(alpha = .54f)
        CampusGlassRole.CONTROL -> PrimarySoft.copy(alpha = .48f)
        CampusGlassRole.DENSE -> Surface.copy(alpha = .68f)
    }
    val activeGlow = if (reduceMotion) 0f else interactionProgress.coerceIn(0f, 1f)

    if (backdrop == null || profile.quality == CampusGlassQuality.PAINTED) {
        return this
            .clip(shape)
            .background(resolvedTint)
            .border(1.dp, Color.White.copy(alpha = .38f), shape)
            .drawBehind {
                if (activeGlow > 0f || effects.glowAtRest) {
                    drawCircle(
                        brush = Brush.radialGradient(
                            listOf(
                                glowColor.copy(alpha = .16f + activeGlow * .18f),
                                Color.Transparent,
                            ),
                            center = Offset(size.width * .76f, size.height * .18f),
                            radius = size.maxDimension * .72f,
                        ),
                        radius = size.maxDimension * .72f,
                        center = Offset(size.width * .76f, size.height * .18f),
                    )
                }
            }
    }

    return this.drawBackdrop(
        backdrop = backdrop,
        shape = { shape },
        effects = {
            if (role != CampusGlassRole.DENSE) vibrancy()
            if (effects.blurRadiusDp > 0f) blur(effects.blurRadiusDp.dp.toPx())
            if (profile.lensEnabled && (effects.lensAtRest || effects.lensOnPress && activeGlow > 0f)) {
                val progress = if (effects.lensAtRest) 1f else activeGlow
                lens(12.dp.toPx() * progress, 22.dp.toPx() * progress)
            }
        },
        highlight = {
            Highlight.Ambient.copy(alpha = .58f + activeGlow * .32f)
        },
        shadow = {
            Shadow(
                radius = if (role == CampusGlassRole.NAVIGATION) 14.dp else 7.dp,
                color = glowColor.copy(alpha = .08f + activeGlow * .12f),
            )
        },
        onDrawSurface = {
            drawRect(lerp(resolvedTint, glowColor.copy(alpha = .18f), activeGlow * .22f))
        },
    )
}

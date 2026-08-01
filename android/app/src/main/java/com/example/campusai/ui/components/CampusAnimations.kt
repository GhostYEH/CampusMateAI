package com.example.campusai.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary

// ──────────────────────────────────────────────
// 1. 脉冲动画（用于通知红点 / 徽标吸引注意）
// ──────────────────────────────────────────────

/**
 * 让 [content] 产生缓慢的脉冲呼吸效果（scale + alpha 微变）。
 * 适合挂在通知红点、未读标记上。
 */
@Composable
fun PulseEffect(
    color: Color = Primary,
    pulseSize: Dp = 8.dp,
    enabled: Boolean = true,
    modifier: Modifier = Modifier,
) {
    val reduceMotion = LocalReduceMotion.current
    if (!enabled || reduceMotion) {
        Box(
            modifier = modifier.size(pulseSize).clip(CircleShape).background(color.copy(alpha = .25f)),
        )
        return
    }
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.35f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse-scale",
    )
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.55f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse-alpha",
    )
    Box(
        modifier = modifier
            .scale(pulseScale)
            .alpha(pulseAlpha)
            .clip(CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .clip(CircleShape)
                .fillMaxSize()
                .background(color.copy(alpha = .24f)),
        )
    }
}

// ──────────────────────────────────────────────
// 2. 数字跳变动画（从旧值滚动到新值）
// ──────────────────────────────────────────────

/**
 * 带有翻转/滚动过渡效果的数字组件。
 * 当 [target] 变化时，数字会从旧值滚动到新值。
 */
@Composable
fun AnimatedCounter(
    target: Int,
    modifier: Modifier = Modifier,
    fontSize: TextUnit = 28.sp,
    fontWeight: FontWeight = FontWeight.Bold,
    color: Color = Primary,
) {
    val reduceMotion = LocalReduceMotion.current
    val displayValue by animateIntAsState(
        targetValue = target,
        animationSpec = if (reduceMotion) snap() else spring(
            dampingRatio = 0.6f,
            stiffness = 120f,
        ),
        label = "counter",
    )
    androidx.compose.material3.Text(
        text = displayValue.toString(),
        fontSize = fontSize,
        fontWeight = fontWeight,
        color = color,
        modifier = modifier,
    )
}

/**
 * 带百分比的数字动画（用于进度百分比）。
 */
@Composable
fun AnimatedPercent(
    target: Int,
    modifier: Modifier = Modifier,
    fontSize: TextUnit = 21.sp,
    fontWeight: FontWeight = FontWeight.Bold,
    color: Color = Primary,
) {
    val reduceMotion = LocalReduceMotion.current
    val displayValue by animateIntAsState(
        targetValue = target,
        animationSpec = if (reduceMotion) snap() else tween(800, easing = CubicBezierEasing(0.22f, 0.82f, 0.2f, 1f)),
        label = "percent",
    )
    androidx.compose.material3.Text(
        text = "${displayValue}%",
        fontSize = fontSize,
        fontWeight = fontWeight,
        color = color,
        modifier = modifier,
    )
}

// ──────────────────────────────────────────────
// 3. 柱状图条动画（从底部升起）
// ──────────────────────────────────────────────

/**
 * 带入场动画的柱状图条。
 * [fraction] 0f~1f 表示高度百分比，[delayMs] 用于交错。
 */
@Composable
fun AnimatedBar(
    fraction: Float,
    delayMs: Int = 0,
    modifier: Modifier = Modifier,
    color: Color = Primary.copy(alpha = 0.6f),
) {
    val reduceMotion = LocalReduceMotion.current
    var animated by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    val heightFraction by animateFloatAsState(
        targetValue = if (animated || reduceMotion) fraction else 0f,
        animationSpec = if (reduceMotion) snap() else tween(
            durationMillis = 600,
            delayMillis = delayMs,
            easing = CubicBezierEasing(0.22f, 0.82f, 0.2f, 1f),
        ),
        label = "bar-height",
    )
    androidx.compose.runtime.LaunchedEffect(Unit) {
        animated = true
    }
    Box(
        modifier = modifier
            .background(color)
            .graphicsLayer { scaleY = heightFraction; transformOrigin = androidx.compose.ui.graphics.TransformOrigin(0.5f, 1f) },
    )
}

// ──────────────────────────────────────────────
// 4. 打字指示器（三个跳动小点）
// ──────────────────────────────────────────────

/**
 * 模拟 AI 正在输入的三个跳动圆点。
 */
@Composable
fun TypingIndicator(
    modifier: Modifier = Modifier,
    dotColor: Color? = null,
    dotSize: Dp = 6.dp,
    enabled: Boolean = true,
) {
    val resolvedDotColor = dotColor ?: Muted
    val reduceMotion = LocalReduceMotion.current
    if (!enabled || reduceMotion) {
        androidx.compose.foundation.layout.Row(
            modifier = modifier,
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(5.dp),
        ) {
            repeat(3) {
                Box(Modifier.size(dotSize).clip(CircleShape).background(resolvedDotColor))
            }
        }
        return
    }
    val infiniteTransition = rememberInfiniteTransition(label = "typing")
    val delays = listOf(0, 200, 400)
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center,
    ) {
        androidx.compose.foundation.layout.Row(
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            delays.forEach { delayMs ->
                val scale by infiniteTransition.animateFloat(
                    initialValue = 1f,
                    targetValue = 0.4f,
                    animationSpec = infiniteRepeatable(
                        animation = tween(600, delayMillis = delayMs, easing = FastOutSlowInEasing),
                        repeatMode = RepeatMode.Reverse,
                    ),
                    label = "typing-dot-$delayMs",
                )
                Box(
                    modifier = Modifier
                        .size(dotSize)
                        .scale(scale)
                        .clip(CircleShape)
                        .background(resolvedDotColor),
                )
            }
        }
    }
}

// ──────────────────────────────────────────────
// 5. 呼吸浮动效果（用于 Hero 卡片等）
// ──────────────────────────────────────────────

/**
 * 让内容产生缓慢上下浮动效果，适合 Hero / 品牌卡片。
 */
@Composable
fun Modifier.breathingFloat(
    enabled: Boolean = true,
    amplitude: Float = 4f,
    periodMs: Int = 3000,
): Modifier {
    if (!enabled || LocalReduceMotion.current) return this
    val infiniteTransition = rememberInfiniteTransition(label = "float")
    val offset by infiniteTransition.animateFloat(
        initialValue = -amplitude,
        targetValue = amplitude,
        animationSpec = infiniteRepeatable(
            animation = tween(periodMs, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "float-offset",
    )
    return this.graphicsLayer { translationY = offset }
}

// ──────────────────────────────────────────────
// 6. 环形进度动画（单段，0→target）
// ──────────────────────────────────────────────

/**
 * 带动画的 [CircularProgressIndicator]，从 0 到 [targetProgress] 平滑过渡。
 */
@Composable
fun AnimatedCircularProgress(
    targetProgress: Float,
    modifier: Modifier = Modifier,
    delayMs: Int = 0,
    color: Color = Primary,
    trackColor: Color? = null,
    strokeWidth: Dp = 7.dp,
) {
    val reduceMotion = LocalReduceMotion.current
    val resolvedTrackColor = trackColor ?: Line.copy(alpha = if (reduceMotion) .55f else .62f)
    var animated by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    val progress by animateFloatAsState(
        targetValue = if (animated || reduceMotion) targetProgress else 0f,
        animationSpec = if (reduceMotion) snap() else tween(1000, delayMillis = delayMs, easing = CubicBezierEasing(0.22f, 0.82f, 0.2f, 1f)),
        label = "progress-ring",
    )
    androidx.compose.runtime.LaunchedEffect(Unit) {
        animated = true
    }
    Box(modifier = modifier) {
        androidx.compose.material3.CircularProgressIndicator(
            progress = { 1f },
            color = resolvedTrackColor,
            strokeWidth = strokeWidth,
            modifier = Modifier.fillMaxSize(),
        )
        androidx.compose.material3.CircularProgressIndicator(
            progress = { progress },
            color = color,
            strokeWidth = strokeWidth,
            modifier = Modifier.fillMaxSize(),
        )
    }
}

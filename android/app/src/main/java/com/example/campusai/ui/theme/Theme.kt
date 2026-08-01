package com.example.campusai.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color

private fun lightScheme(colors: CampusColors) = lightColorScheme(
    primary = colors.primary,
    onPrimary = colors.surface,
    primaryContainer = colors.primarySoft,
    onPrimaryContainer = colors.primaryHover,
    secondary = colors.accent,
    onSecondary = colors.surface,
    secondaryContainer = Color(0xFFF0E6DA),
    onSecondaryContainer = Color(0xFF5A3821),
    tertiary = colors.success,
    error = colors.danger,
    onError = colors.surface,
    errorContainer = colors.alertErrorBg,
    onErrorContainer = colors.alertErrorText,
    background = colors.background,
    onBackground = colors.textPrimary,
    surface = colors.surface,
    onSurface = colors.textPrimary,
    surfaceVariant = colors.background,
    onSurfaceVariant = colors.muted,
    outline = colors.line,
    outlineVariant = colors.inputBorder,
)

private fun darkScheme(colors: CampusColors) = darkColorScheme(
    primary = colors.primary,
    onPrimary = colors.background,
    primaryContainer = colors.primarySoft,
    onPrimaryContainer = colors.primary,
    secondary = colors.accent,
    onSecondary = colors.background,
    secondaryContainer = Color(0xFF4A3325),
    onSecondaryContainer = Color(0xFFFFDCC4),
    tertiary = colors.success,
    onTertiary = colors.background,
    error = colors.danger,
    onError = colors.background,
    errorContainer = colors.alertErrorBg,
    onErrorContainer = colors.alertErrorText,
    background = colors.background,
    onBackground = colors.textPrimary,
    surface = colors.surface,
    onSurface = colors.textPrimary,
    surfaceVariant = colors.primarySoft,
    onSurfaceVariant = colors.muted,
    outline = colors.line,
    outlineVariant = colors.inputBorder,
)

private val ThemeTransitionEasing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f)

@Composable
private fun animateThemeColor(
    target: Color,
    reduceMotion: Boolean,
    label: String,
): Color {
    val value by animateColorAsState(
        targetValue = target,
        animationSpec = if (reduceMotion) {
            snap()
        } else {
            tween(durationMillis = 420, easing = ThemeTransitionEasing)
        },
        label = label,
    )
    return value
}

@Composable
private fun CampusColors.animated(reduceMotion: Boolean): CampusColors = copy(
    primary = animateThemeColor(primary, reduceMotion, "theme-primary"),
    primaryHover = animateThemeColor(primaryHover, reduceMotion, "theme-primary-hover"),
    primarySoft = animateThemeColor(primarySoft, reduceMotion, "theme-primary-soft"),
    accent = animateThemeColor(accent, reduceMotion, "theme-accent"),
    danger = animateThemeColor(danger, reduceMotion, "theme-danger"),
    success = animateThemeColor(success, reduceMotion, "theme-success"),
    textPrimary = animateThemeColor(textPrimary, reduceMotion, "theme-text"),
    muted = animateThemeColor(muted, reduceMotion, "theme-muted"),
    line = animateThemeColor(line, reduceMotion, "theme-line"),
    surface = animateThemeColor(surface, reduceMotion, "theme-surface"),
    background = animateThemeColor(background, reduceMotion, "theme-background"),
    dangerText = animateThemeColor(dangerText, reduceMotion, "theme-danger-text"),
    successText = animateThemeColor(successText, reduceMotion, "theme-success-text"),
    loginBg = animateThemeColor(loginBg, reduceMotion, "theme-login-bg"),
    loginShadeStart = animateThemeColor(loginShadeStart, reduceMotion, "theme-login-shade-start"),
    loginShadeMid = animateThemeColor(loginShadeMid, reduceMotion, "theme-login-shade-mid"),
    loginShadeEnd = animateThemeColor(loginShadeEnd, reduceMotion, "theme-login-shade-end"),
    loginPanelBg = animateThemeColor(loginPanelBg, reduceMotion, "theme-login-panel"),
    sidebarActiveBg = animateThemeColor(sidebarActiveBg, reduceMotion, "theme-sidebar-bg"),
    sidebarActiveText = animateThemeColor(sidebarActiveText, reduceMotion, "theme-sidebar-text"),
    avatarBg = animateThemeColor(avatarBg, reduceMotion, "theme-avatar"),
    chatAssistantBg = animateThemeColor(chatAssistantBg, reduceMotion, "theme-chat-assistant"),
    chatUserBg = animateThemeColor(chatUserBg, reduceMotion, "theme-chat-user"),
    robotAvatarBg = animateThemeColor(robotAvatarBg, reduceMotion, "theme-robot-avatar"),
    modeBadgeDot = animateThemeColor(modeBadgeDot, reduceMotion, "theme-mode-dot"),
    mockBadgeBg = animateThemeColor(mockBadgeBg, reduceMotion, "theme-mock-bg"),
    mockBadgeText = animateThemeColor(mockBadgeText, reduceMotion, "theme-mock-text"),
    unreadDot = animateThemeColor(unreadDot, reduceMotion, "theme-unread-dot"),
    pendingBadgeBg = animateThemeColor(pendingBadgeBg, reduceMotion, "theme-pending-bg"),
    pendingBadgeText = animateThemeColor(pendingBadgeText, reduceMotion, "theme-pending-text"),
    focusRing = animateThemeColor(focusRing, reduceMotion, "theme-focus-ring"),
    inputBorder = animateThemeColor(inputBorder, reduceMotion, "theme-input-border"),
    inputFocusBorder = animateThemeColor(inputFocusBorder, reduceMotion, "theme-input-focus"),
    inputFocusShadow = animateThemeColor(inputFocusShadow, reduceMotion, "theme-input-shadow"),
    alertErrorBg = animateThemeColor(alertErrorBg, reduceMotion, "theme-error-bg"),
    alertErrorText = animateThemeColor(alertErrorText, reduceMotion, "theme-error-text"),
    alertInfoBg = animateThemeColor(alertInfoBg, reduceMotion, "theme-info-bg"),
    alertInfoText = animateThemeColor(alertInfoText, reduceMotion, "theme-info-text"),
)

@Composable
fun CampusAITheme(
    darkTheme: Boolean = false,
    reduceMotion: Boolean = false,
    content: @Composable () -> Unit,
) {
    val targetColors = if (darkTheme) DarkCampusColors else LightCampusColors
    val colors = targetColors.animated(reduceMotion)
    CompositionLocalProvider(LocalCampusColors provides colors) {
        MaterialTheme(
            colorScheme = if (darkTheme) darkScheme(colors) else lightScheme(colors),
            typography = AppTypography,
        ) {
            CompositionLocalProvider(
                LocalContentColor provides colors.textPrimary,
                LocalReduceMotion provides reduceMotion,
            ) {
                ProvideCampusIndication {
                    content()
                }
            }
        }
    }
}

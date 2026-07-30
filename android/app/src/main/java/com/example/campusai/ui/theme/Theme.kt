package com.example.campusai.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Color

private fun lightScheme(colors: CampusColors) = lightColorScheme(
    primary = colors.primary,
    onPrimary = colors.surface,
    primaryContainer = colors.primarySoft,
    onPrimaryContainer = colors.primaryHover,
    secondary = colors.accent,
    onSecondary = colors.surface,
    secondaryContainer = Color(0xFFF0E6DA),
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
    onPrimary = Color(0xFF102D3D),
    primaryContainer = colors.primarySoft,
    onPrimaryContainer = colors.primary,
    secondary = colors.accent,
    onSecondary = colors.background,
    tertiary = colors.success,
    error = colors.danger,
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

@Composable
fun CampusAITheme(
    darkTheme: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkCampusColors else LightCampusColors
    CompositionLocalProvider(LocalCampusColors provides colors) {
        MaterialTheme(
            colorScheme = if (darkTheme) darkScheme(colors) else lightScheme(colors),
            typography = AppTypography,
        ) {
            CompositionLocalProvider(LocalContentColor provides colors.textPrimary) {
                content()
            }
        }
    }
}

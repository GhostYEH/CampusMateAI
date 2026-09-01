package com.example.campusai.ui.components

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Button as MaterialButton
import androidx.compose.material3.ButtonColors
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ButtonElevation
import androidx.compose.material3.Card as MaterialCard
import androidx.compose.material3.CardColors
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CardElevation
import androidx.compose.material3.ExtendedFloatingActionButton as MaterialExtendedFloatingActionButton
import androidx.compose.material3.FloatingActionButton as MaterialFloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.FloatingActionButtonElevation
import androidx.compose.material3.IconButton as MaterialIconButton
import androidx.compose.material3.IconButtonColors
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.OutlinedButton as MaterialOutlinedButton
import androidx.compose.material3.TextButton as MaterialTextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.glass.CampusGlassRole
import com.example.campusai.ui.glass.campusGlass
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft

@Composable
private fun glassControlModifier(
    modifier: Modifier,
    shape: Shape,
    enabled: Boolean,
    interactionSource: MutableInteractionSource,
    tint: Color,
): Modifier {
    val pressed by interactionSource.collectIsPressedAsState()
    val reduceMotion = LocalReduceMotion.current
    val progress by animateFloatAsState(
        targetValue = if (pressed && enabled && !reduceMotion) 1f else 0f,
        animationSpec = spring(dampingRatio = .84f, stiffness = 760f),
        label = "glass-control-glow",
    )
    return modifier.campusGlass(
        shape = shape,
        role = CampusGlassRole.CONTROL,
        tint = tint.copy(alpha = if (enabled) .52f else .30f),
        interactionProgress = progress,
        glowColor = Primary,
    )
}

private fun transparentButtonColors(colors: ButtonColors): ButtonColors = ButtonColors(
    containerColor = Color.Transparent,
    contentColor = colors.contentColor,
    disabledContainerColor = Color.Transparent,
    disabledContentColor = colors.disabledContentColor,
)

@Composable
fun GlassButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = ButtonDefaults.shape,
    colors: ButtonColors = ButtonDefaults.buttonColors(),
    elevation: ButtonElevation? = ButtonDefaults.buttonElevation(),
    border: BorderStroke? = null,
    contentPadding: PaddingValues = ButtonDefaults.ContentPadding,
    interactionSource: MutableInteractionSource? = null,
    content: @Composable RowScope.() -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialButton(
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, enabled, resolvedInteractionSource, colors.containerColor),
        enabled = enabled,
        shape = shape,
        colors = transparentButtonColors(colors),
        elevation = elevation,
        border = border,
        contentPadding = contentPadding,
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

@Composable
fun GlassOutlinedButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = ButtonDefaults.outlinedShape,
    colors: ButtonColors = ButtonDefaults.outlinedButtonColors(),
    elevation: ButtonElevation? = null,
    border: BorderStroke? = ButtonDefaults.outlinedButtonBorder,
    contentPadding: PaddingValues = ButtonDefaults.ContentPadding,
    interactionSource: MutableInteractionSource? = null,
    content: @Composable RowScope.() -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialOutlinedButton(
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, enabled, resolvedInteractionSource, PrimarySoft),
        enabled = enabled,
        shape = shape,
        colors = transparentButtonColors(colors),
        elevation = elevation,
        border = border,
        contentPadding = contentPadding,
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

@Composable
fun GlassTextButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = ButtonDefaults.textShape,
    colors: ButtonColors = ButtonDefaults.textButtonColors(),
    elevation: ButtonElevation? = null,
    border: BorderStroke? = null,
    contentPadding: PaddingValues = ButtonDefaults.TextButtonContentPadding,
    interactionSource: MutableInteractionSource? = null,
    content: @Composable RowScope.() -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialTextButton(
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, enabled, resolvedInteractionSource, PrimarySoft),
        enabled = enabled,
        shape = shape,
        colors = transparentButtonColors(colors),
        elevation = elevation,
        border = border,
        contentPadding = contentPadding,
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

@Composable
fun GlassIconButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    colors: IconButtonColors = IconButtonDefaults.iconButtonColors(),
    interactionSource: MutableInteractionSource? = null,
    content: @Composable () -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialIconButton(
        onClick = onClick,
        modifier = glassControlModifier(modifier, CircleShape, enabled, resolvedInteractionSource, PrimarySoft),
        enabled = enabled,
        colors = IconButtonDefaults.iconButtonColors(
            containerColor = Color.Transparent,
            contentColor = colors.contentColor,
            disabledContainerColor = Color.Transparent,
            disabledContentColor = colors.disabledContentColor,
        ),
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

@Composable
fun GlassFloatingActionButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    shape: Shape = FloatingActionButtonDefaults.shape,
    containerColor: Color = Primary,
    contentColor: Color = Color.White,
    elevation: FloatingActionButtonElevation = FloatingActionButtonDefaults.elevation(),
    interactionSource: MutableInteractionSource? = null,
    content: @Composable () -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialFloatingActionButton(
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, true, resolvedInteractionSource, containerColor),
        shape = shape,
        containerColor = Color.Transparent,
        contentColor = contentColor,
        elevation = elevation,
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

@Composable
fun GlassExtendedFloatingActionButton(
    text: @Composable () -> Unit,
    icon: @Composable () -> Unit,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    expanded: Boolean = true,
    shape: Shape = FloatingActionButtonDefaults.extendedFabShape,
    containerColor: Color = Primary,
    contentColor: Color = Color.White,
    elevation: FloatingActionButtonElevation = FloatingActionButtonDefaults.elevation(),
    interactionSource: MutableInteractionSource? = null,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialExtendedFloatingActionButton(
        text = text,
        icon = icon,
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, true, resolvedInteractionSource, containerColor),
        expanded = expanded,
        shape = shape,
        containerColor = Color.Transparent,
        contentColor = contentColor,
        elevation = elevation,
        interactionSource = resolvedInteractionSource,
    )
}

private fun transparentCardColors(colors: CardColors): CardColors = CardColors(
    containerColor = Color.Transparent,
    contentColor = colors.contentColor,
    disabledContainerColor = Color.Transparent,
    disabledContentColor = colors.disabledContentColor,
)

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    shape: Shape = CardDefaults.shape,
    colors: CardColors = CardDefaults.cardColors(),
    elevation: CardElevation = CardDefaults.cardElevation(),
    border: BorderStroke? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    MaterialCard(
        // Cards are frequently repeated in lazy lists, so they use the
        // lightweight glass stack without blur/lens at rest.
        modifier = modifier.campusGlass(
            shape = shape,
            role = CampusGlassRole.DENSE,
            tint = colors.containerColor,
        ),
        shape = shape,
        colors = transparentCardColors(colors),
        elevation = elevation,
        border = border,
        content = content,
    )
}

@Composable
fun GlassCard(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    shape: Shape = CardDefaults.shape,
    colors: CardColors = CardDefaults.cardColors(),
    elevation: CardElevation = CardDefaults.cardElevation(),
    border: BorderStroke? = null,
    interactionSource: MutableInteractionSource? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val resolvedInteractionSource = interactionSource ?: remember { MutableInteractionSource() }
    MaterialCard(
        onClick = onClick,
        modifier = glassControlModifier(modifier, shape, enabled, resolvedInteractionSource, colors.containerColor),
        enabled = enabled,
        shape = shape,
        colors = transparentCardColors(colors),
        elevation = elevation,
        border = border,
        interactionSource = resolvedInteractionSource,
        content = content,
    )
}

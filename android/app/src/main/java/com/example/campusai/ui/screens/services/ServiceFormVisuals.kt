package com.example.campusai.ui.screens.services

import androidx.annotation.DrawableRes
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.components.breathingFloat
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.InputBorder
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private val FormRadius = RoundedCornerShape(26.dp)
private val FieldRadius = RoundedCornerShape(17.dp)

@Composable
internal fun ServiceHeroHeader(
    title: String,
    subtitle: String,
    @DrawableRes heroImage: Int,
    onBack: () -> Unit,
    showBack: Boolean = true,
) {
    val reduceMotion = LocalReduceMotion.current
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(178.dp),
    ) {
        Column(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(top = 12.dp),
        ) {
            Spacer(Modifier.height(42.dp))
            Text(title, color = TextPrimary, fontSize = 30.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-.5).sp)
            Spacer(Modifier.height(7.dp))
            Text(subtitle, color = Muted, fontSize = 14.sp, lineHeight = 20.sp)
        }
        androidx.compose.foundation.Image(
            painter = painterResource(heroImage),
            contentDescription = null,
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 2.dp, end = (-4).dp)
                .size(width = 202.dp, height = 168.dp)
                .breathingFloat(enabled = !reduceMotion, amplitude = 2f, periodMs = 3400),
        )
    }
}

@Composable
internal fun ServiceFormCard(content: @Composable () -> Unit) {
    val reduceMotion = LocalReduceMotion.current
    AnimatedVisibility(
        visible = true,
        enter = fadeIn(tween(if (reduceMotion) 0 else 260)) +
            slideInVertically(tween(if (reduceMotion) 0 else 330)) { it / 14 },
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(14.dp, FormRadius, ambientColor = Color(0x123C5B90), spotColor = Color(0x123C5B90))
                .clip(FormRadius)
                .background(Surface)
                .border(1.dp, Color.White.copy(alpha = .8f), FormRadius)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) { content() }
    }
}

@Composable
internal fun ServiceSection(label: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(width = 4.dp, height = 22.dp).clip(CircleShape).background(Primary))
            Spacer(Modifier.width(11.dp))
            Text(label, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        }
        content()
    }
}

@Composable
internal fun ServiceOptionRow(
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
        items(options, key = { it }) { option ->
            val active = option == selected
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(16.dp))
                    .background(if (active) PrimarySoft.copy(alpha = .7f) else Surface)
                    .border(1.dp, if (active) Primary else InputBorder, RoundedCornerShape(16.dp))
                    .campusClickable { onSelect(option) }
                    .padding(horizontal = 17.dp, vertical = 12.dp),
            ) {
                Text(option, color = if (active) Primary else Muted, fontWeight = if (active) FontWeight.Bold else FontWeight.Medium, fontSize = 14.sp)
            }
        }
    }
}

@Composable
internal fun ServiceInput(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    icon: ImageVector? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    lines: Int = 1,
    maxLength: Int? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(if (lines > 1) 144.dp else 58.dp)
            .clip(FieldRadius)
            .background(Surface)
            .border(1.dp, InputBorder, FieldRadius)
            .padding(horizontal = 16.dp, vertical = if (lines > 1) 15.dp else 0.dp),
        verticalAlignment = if (lines > 1) Alignment.Top else Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = Muted, modifier = Modifier.size(22.dp))
            Spacer(Modifier.width(12.dp))
        }
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) Text(placeholder, color = Muted.copy(alpha = .72f), fontSize = 14.sp)
            BasicTextField(
                value = value,
                onValueChange = { onValueChange(maxLength?.let { max -> it.take(max) } ?: it) },
                textStyle = TextStyle(color = TextPrimary, fontSize = 14.sp),
                cursorBrush = SolidColor(Primary),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = keyboardType),
                minLines = lines,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        if (maxLength != null && lines > 1) {
            Text("${value.length} / $maxLength", color = Muted, fontSize = 12.sp, modifier = Modifier.align(Alignment.Bottom))
        }
    }
}

@Composable
internal fun ServiceSelectField(
    options: List<String>,
    selected: String,
    placeholder: String,
    icon: ImageVector,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(58.dp)
                .clip(FieldRadius)
                .background(Surface)
                .border(1.dp, InputBorder, FieldRadius)
                .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null) { expanded = true }
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(icon, null, tint = Muted, modifier = Modifier.size(22.dp))
            Spacer(Modifier.width(12.dp))
            Text(selected.ifBlank { placeholder }, color = if (selected.isBlank()) Muted.copy(alpha = .72f) else TextPrimary, fontSize = 14.sp, modifier = Modifier.weight(1f))
            Icon(Icons.Default.ArrowDropDown, null, tint = Muted, modifier = Modifier.size(24.dp))
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option, color = if (option == selected) Primary else TextPrimary) },
                    onClick = { onSelect(option); expanded = false },
                )
            }
        }
    }
}

@Composable
internal fun ServiceNotice(text: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("ⓘ", color = Muted, fontSize = 18.sp)
        Spacer(Modifier.width(9.dp))
        Text(text, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
    }
}

@Composable
internal fun ServiceSubmitButton(text: String, enabled: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(57.dp)
            .shadow(12.dp, RoundedCornerShape(18.dp), ambientColor = Primary.copy(alpha = .2f), spotColor = Primary.copy(alpha = .2f))
            .clip(RoundedCornerShape(18.dp))
            .background(if (enabled) Brush.horizontalGradient(listOf(Color(0xFF6173F7), Color(0xFF2556F3))) else Brush.horizontalGradient(listOf(PrimarySoft, PrimarySoft)))
            .campusClickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, color = Color.White, fontSize = 19.sp, fontWeight = FontWeight.Bold)
    }
}

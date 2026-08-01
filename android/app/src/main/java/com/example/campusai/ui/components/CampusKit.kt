package com.example.campusai.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.theme.Accent

/** 统一的状态标签色调，全部取自现有设计 Token，不新增颜色。 */
enum class StatusTone { INFO, SUCCESS, WARNING, DANGER, NEUTRAL }

@Composable
fun StatusTag(text: String, tone: StatusTone, modifier: Modifier = Modifier) {
    val (bg, fg) = when (tone) {
        StatusTone.INFO -> PrimarySoft to Primary
        StatusTone.SUCCESS -> Success.copy(alpha = .14f) to Success
        StatusTone.WARNING -> Accent.copy(alpha = .14f) to Accent
        StatusTone.DANGER -> DangerText.copy(alpha = .12f) to DangerText
        StatusTone.NEUTRAL -> Background to Muted
    }
    Text(
        text = text,
        color = fg,
        fontSize = 10.5.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = modifier
            .clip(CircleShape)
            .background(bg)
            .padding(horizontal = 9.dp, vertical = 4.dp),
    )
}

/** 统一卡片容器：白色圆角 + 浅色边框，与现有页面一致。 */
@Composable
fun CampusCard(
    modifier: Modifier = Modifier,
    padding: PaddingValues = PaddingValues(16.dp),
    content: @Composable () -> Unit,
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(18.dp))
            .padding(padding),
    ) { content() }
}

/** 二级页面统一标题栏：返回按钮 + 标题 + 副标题 + 右侧操作位。 */
@Composable
fun CampusPageHeader(
    title: String,
    subtitle: String? = null,
    onBack: (() -> Unit)? = null,
    actions: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .shadow(
                        elevation = 9.dp,
                        shape = CircleShape,
                        ambientColor = Color(0x1F24365A),
                        spotColor = Color(0x1F24365A),
                    )
                    .clip(CircleShape)
                    .background(Surface)
                    .campusClickable(role = androidx.compose.ui.semantics.Role.Button, onClick = onBack),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = CampusStrings.Common.BACK,
                    tint = TextPrimary,
                    modifier = Modifier.size(25.dp),
                )
            }
            Spacer(Modifier.width(16.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.titleLarge,
                color = TextPrimary,
                fontWeight = FontWeight.Bold,
            )
            if (subtitle != null) {
                Text(subtitle, color = Muted, fontSize = 12.sp)
            }
        }
        actions?.invoke()
    }
}

/** 筛选 Chip 行（单选）。 */
@Composable
fun FilterChipRow(
    options: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyRow(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(options, key = { it }) { option ->
            val active = option == selected
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(if (active) PrimarySoft else Surface)
                    .border(1.dp, if (active) Primary else Line, CircleShape)
                    .campusClickable { onSelect(option) }
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            ) {
                Text(
                    option,
                    color = if (active) Primary else Muted,
                    fontSize = 12.sp,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                )
            }
        }
    }
}

/** 多选 Chip 组（节次等场景）。 */
@Composable
fun MultiSelectChipRow(
    options: List<String>,
    selected: Set<String>,
    onToggle: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyRow(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(options, key = { it }) { option ->
            val active = option in selected
            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(if (active) PrimarySoft else Surface)
                    .border(1.dp, if (active) Primary else Line, CircleShape)
                    .campusClickable { onToggle(option) }
                    .padding(horizontal = 12.dp, vertical = 7.dp),
            ) {
                Text(
                    option,
                    color = if (active) Primary else Muted,
                    fontSize = 11.5.sp,
                    fontWeight = if (active) FontWeight.SemiBold else FontWeight.Normal,
                )
            }
        }
    }
}

/** 加载状态。 */
@Composable
fun LoadingState(message: String = CampusStrings.Common.LOADING, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 200.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(color = Primary, strokeWidth = 3.dp, modifier = Modifier.size(32.dp))
        Spacer(Modifier.height(12.dp))
        Text(message, color = Muted, style = MaterialTheme.typography.bodySmall)
    }
}

/** 错误状态（含重试）。 */
@Composable
fun ErrorState(message: String, onRetry: () -> Unit, modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .defaultMinSize(minHeight = 200.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(Icons.Default.ErrorOutline, null, tint = DangerText, modifier = Modifier.size(36.dp))
        Spacer(Modifier.height(10.dp))
        Text(message, color = Muted, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(12.dp))
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(10.dp))
                .background(Primary)
                .campusClickable(onClick = onRetry)
                .padding(horizontal = 22.dp, vertical = 9.dp),
        ) {
            Text(CampusStrings.Common.RETRY, color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** 统一二次确认弹窗。 */
@Composable
fun ConfirmDialog(
    title: String,
    message: String,
    confirmText: String = CampusStrings.Common.CONFIRM,
    danger: Boolean = false,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title, fontWeight = FontWeight.Bold) },
        text = { Text(message, color = Muted) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(
                    confirmText,
                    color = if (danger) DangerText else Primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(CampusStrings.Common.CANCEL, color = Muted)
            }
        },
        containerColor = Surface,
        shape = RoundedCornerShape(20.dp),
    )
}

/** 通用的页面空状态图标容器（配合 EmptyState 使用）。 */
@Composable
fun PageEmptyState(icon: ImageVector, message: String, modifier: Modifier = Modifier) {
    EmptyState(icon = icon, message = message, modifier = modifier.fillMaxSize())
}

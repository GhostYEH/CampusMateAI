package com.example.campusai.ui.screens.focus

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface as CampusSurface
import com.example.campusai.ui.theme.TextPrimary
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding

/** A terminal page for one completed session. It owns no timer or active-session state. */
@Composable
fun FocusSummaryScreen(
    actualSeconds: Int,
    taskName: String,
    conversationCount: Int,
    aiSummary: String,
    observationSummary: String,
    nextStepTitle: String? = null,
    planComplete: Boolean = false,
    onReturnHome: () -> Unit,
    onStartNext: () -> Unit,
) {
    BackHandler(onBack = onReturnHome)
    val minutes = actualSeconds.coerceAtLeast(0) / 60
    val seconds = actualSeconds.coerceAtLeast(0) % 60
    val duration = if (minutes > 0) "$minutes 分 ${seconds.toString().padStart(2, '0')} 秒" else "$seconds 秒"
    val bottomContentPadding = floatingDockContentBottomPadding(
        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
    ) + 12.dp
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(start = 20.dp, top = 48.dp, end = 20.dp, bottom = bottomContentPadding),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { Surface(shape = CircleShape, color = PrimarySoft) { Icon(Icons.Default.CheckCircle, null, tint = Primary, modifier = Modifier.padding(16.dp)) } }
        item { Text("本次专注总结", color = TextPrimary, fontSize = 28.sp, fontWeight = FontWeight.ExtraBold) }
        item { Text("本次专注已完成 · CampusMate AI 已为你整理这段学习", color = Muted, fontSize = 14.sp) }
        item {
            Surface(shape = RoundedCornerShape(28.dp), color = PrimarySoft.copy(alpha = .72f), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.fillMaxWidth().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    Text(duration, color = TextPrimary, fontSize = 38.sp, fontWeight = FontWeight.ExtraBold)
                    Text("本次学习 · $taskName", color = Muted, fontSize = 14.sp)
                    Text("✓ 已完成", color = Primary, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            }
        }
        item { SummaryNote(Icons.Default.AutoAwesome, "AI 学习总结", aiSummary) }
        item { SummaryNote(Icons.Default.ChatBubbleOutline, "AI 交流", "本次共交流 $conversationCount 次。") }
        item { SummaryNote(Icons.Default.Timer, "学习状态", observationSummary) }
        if (planComplete) {
            item { SummaryNote(Icons.Default.CheckCircle, "任务进度", "这项任务的规划步骤已全部完成。") }
        } else {
            nextStepTitle?.takeIf { it.isNotBlank() }?.let { next ->
                item { SummaryNote(Icons.Default.ArrowForward, "下一步", next) }
            }
        }
        item {
            Spacer(Modifier.height(8.dp))
            Button(onClick = onStartNext, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(18.dp)) {
                Text(if (planComplete) "返回专注大厅" else if (!nextStepTitle.isNullOrBlank()) "开始下一步骤" else "开始下一次专注")
            }
        }
        item {
            OutlinedButton(onClick = onReturnHome, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(18.dp)) { Text("返回专注大厅") }
        }
    }
}

@Composable
private fun SummaryNote(icon: androidx.compose.ui.graphics.vector.ImageVector, title: String, content: String) {
    Surface(shape = RoundedCornerShape(20.dp), color = CampusSurface, modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
            Surface(shape = CircleShape, color = PrimarySoft) { Icon(icon, null, tint = Primary, modifier = Modifier.padding(8.dp)) }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Text(content, color = Muted, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }
    }
}

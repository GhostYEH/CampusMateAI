package com.example.campusai.ui.screens.focus

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.focus.scene.FocusScenePreferenceStore

private val SummaryInk = FocusStudyPalette.Ink

/** A terminal page for one completed session. It owns no timer or active-session state. */
@Composable
fun FocusSummaryScreen(
    selfReport: String? = null,
    actualSeconds: Int,
    taskName: String,
    conversationCount: Int,
    nextStepTitle: String? = null,
    planComplete: Boolean = false,
    onReturnHome: () -> Unit,
    onStartNext: () -> Unit,
    onOpenHistory: () -> Unit,
) {
    BackHandler(onBack = onReturnHome)
    val context = LocalContext.current
    val scene = remember(context) { FocusScenePreferenceStore(context).load().scene }
    val minutes = actualSeconds.coerceAtLeast(0) / 60
    val seconds = actualSeconds.coerceAtLeast(0) % 60
    val duration = if (minutes > 0) "$minutes 分 ${seconds.toString().padStart(2, '0')} 秒" else "$seconds 秒"
    val bottomPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 24.dp

    Box(Modifier.fillMaxSize().background(Color(0xFF132A35))) {
        Image(
            painter = painterResource(scene.backgroundResource()),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize(),
        )
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xC015302A), Color(0xE0132926)))))
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            contentPadding = PaddingValues(start = 20.dp, top = 12.dp, end = 20.dp, bottom = bottomPadding),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onReturnHome) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "返回自习室", tint = Color.White)
                    }
                    Text("本次专注", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
                }
            }
            item { Surface(shape = CircleShape, color = FocusStudyPalette.Paper) {
                Icon(Icons.Default.CheckCircle, null, tint = FocusStudyPalette.Pine, modifier = Modifier.padding(15.dp))
            } }
            item { Text(if (actualSeconds >= 60) "这段学习，完成了" else "这段学习，已结束", color = Color.White, fontSize = 27.sp, fontWeight = FontWeight.ExtraBold) }
            item { Text("这次的收获，已经留在学习足迹里", color = Color.White.copy(alpha = .86f), fontSize = 14.sp) }
            item {
                Surface(shape = RoundedCornerShape(26.dp), color = FocusStudyPalette.Pine,
                    border = BorderStroke(1.dp, Color.White.copy(alpha = .16f)), modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth().padding(21.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(7.dp)) {
                        Text("本次专注", color = Color(0xFFFFE5B9), fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        Text(duration, color = Color.White, fontSize = 36.sp, fontWeight = FontWeight.ExtraBold)
                        Text(taskName, color = Color.White.copy(alpha = .86f), fontSize = 14.sp)
                        Text(if (actualSeconds >= 60) "✓ 已完成" else "已结束 · 不足 1 分钟",
                            color = Color(0xFFFFE5B9), fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    }
                }
            }
            item { SummaryNote(Icons.Default.AutoAwesome, "我的学习收获", selfReport?.takeIf { it.isNotBlank() } ?: "这次还没有记录收获。下次结束时，可以写下一件完成的事。") }
            if (conversationCount > 0) item { SummaryNote(Icons.Default.ChatBubbleOutline, "AI 交流", "本次共交流 $conversationCount 次。") }
            if (planComplete) {
                item { SummaryNote(Icons.Default.CheckCircle, "任务进度", "这项任务的规划步骤已全部完成。") }
            } else {
                nextStepTitle?.takeIf { it.isNotBlank() }?.let { next ->
                    item { SummaryNote(Icons.Default.ArrowForward, "下一步", next) }
                }
            }
            item {
                Spacer(Modifier.height(18.dp))
                Button(
                    onClick = onStartNext,
                    modifier = Modifier.fillMaxWidth().height(52.dp),
                    shape = RoundedCornerShape(18.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = FocusStudyPalette.Pine, contentColor = Color.White),
                ) {
                    Text(if (!planComplete && !nextStepTitle.isNullOrBlank()) "开始下一步骤" else "返回自习室", fontWeight = FontWeight.Bold)
                }
            }
            item {
                OutlinedButton(
                    onClick = onOpenHistory,
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    shape = RoundedCornerShape(18.dp),
                    border = BorderStroke(1.dp, Color.White.copy(alpha = .7f)),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Color.White),
                ) { Text("查看学习足迹") }
            }
        }
    }
}

@Composable
private fun SummaryNote(icon: ImageVector, title: String, content: String) {
    Surface(shape = RoundedCornerShape(20.dp), color = FocusStudyPalette.Paper,
        border = BorderStroke(1.dp, FocusStudyPalette.Line), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(15.dp), verticalAlignment = Alignment.Top) {
            Surface(shape = CircleShape, color = FocusStudyPalette.PaperSoft) {
                Icon(icon, null, tint = FocusStudyPalette.Pine, modifier = Modifier.padding(8.dp).size(18.dp))
            }
            Spacer(Modifier.size(11.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, color = SummaryInk, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                Text(content, color = FocusStudyPalette.Muted, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }
    }
}

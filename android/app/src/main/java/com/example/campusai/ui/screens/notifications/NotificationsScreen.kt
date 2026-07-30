package com.example.campusai.ui.screens.notifications

import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.ExtractResult
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun NotificationsScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val scope = rememberCoroutineScope()

    var noticeText by remember {
        mutableStateOf("【教务处通知】请各班同学于本周五17:00前完成2026年秋季学期选课确认，登录教务系统核对课程信息。如有冲突请联系学院教务办公室。")
    }
    var extracting by remember { mutableStateOf(false) }
    var extracted by remember { mutableStateOf<ExtractResult?>(null) }

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp)
            .graphicsLayer { alpha = animatedAlpha }
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text("通知整理", style = MaterialTheme.typography.headlineMedium)
                Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
            }
            ModeBadge(mockMode)
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text("粘贴校园通知", style = MaterialTheme.typography.titleMedium)
            Text(
                "系统会尝试提取标题、来源、截止时间与待办。结果需要你确认后保存。",
                color = Muted, fontSize = 12.sp
            )
            OutlinedTextField(
                value = noticeText,
                onValueChange = { noticeText = it },
                modifier = Modifier.fillMaxWidth().height(180.dp),
                shape = RoundedCornerShape(8.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = InputBorder
                )
            )
            Button(
                onClick = {
                    scope.launch {
                        extracting = true
                        try { extracted = repository.extractNotice(noticeText) }
                        catch (e: Exception) { extracted = ExtractResult(error = "提取服务暂时不可用，请稍后重试。") }
                        finally { extracting = false }
                    }
                },
                enabled = !extracting && noticeText.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(8.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary)
            ) {
                if (extracting) {
                    CircularProgressIndicator(modifier = Modifier.size(18.dp), color = Surface, strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("正在智能提取…", fontWeight = FontWeight.SemiBold)
                } else {
                    Text("开始提取", fontWeight = FontWeight.SemiBold)
                    Icon(Icons.Default.AutoAwesome, null, modifier = Modifier.size(18.dp))
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(10.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(10.dp))
                .padding(22.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Text("提取结果", style = MaterialTheme.typography.titleMedium)

            val result = extracted
            if (result == null) {
                Column(
                    modifier = Modifier.fillMaxWidth().height(120.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Icon(Icons.Default.ContentPaste, null, tint = Muted, modifier = Modifier.size(42.dp))
                    Spacer(Modifier.height(10.dp))
                    Text("提取结果会显示在这里", color = Muted, fontSize = 12.sp)
                }
            } else if (result.error != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(AlertErrorBg)
                        .padding(10.dp, 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Warning, null, tint = AlertErrorText, modifier = Modifier.size(16.dp))
                    Text(result.error, color = AlertErrorText, fontSize = 13.sp)
                }
            } else {
                var editTitle by remember(result) { mutableStateOf(result.title) }
                var editSource by remember(result) { mutableStateOf(result.source) }
                var editDeadline by remember(result) { mutableStateOf(result.deadline) }

                OutlinedTextField(value = editTitle, onValueChange = { editTitle = it }, label = { Text("标题") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))
                OutlinedTextField(value = editSource, onValueChange = { editSource = it }, label = { Text("来源") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))
                OutlinedTextField(value = editDeadline, onValueChange = { editDeadline = it }, label = { Text("截止时间") }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(8.dp), colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Primary, unfocusedBorderColor = InputBorder))

                if (result.tasks.isNotEmpty()) {
                    Text("识别出的事项", fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                    result.tasks.forEach { task ->
                        Text("• $task", fontSize = 13.sp, color = TextPrimary)
                    }
                }

                Text(
                    "置信度 ${Math.round(result.confidence * 100)}%，结果仅供确认。",
                    color = Muted, fontSize = 12.sp
                )

                Button(
                    onClick = {
                        scope.launch {
                            repository.addTask(editTitle, editDeadline)
                            extracted = result.copy(saved = true)
                        }
                    },
                    enabled = !result.saved,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary)
                ) {
                    Text(if (result.saved) "已保存到待办" else "确认并保存", fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}


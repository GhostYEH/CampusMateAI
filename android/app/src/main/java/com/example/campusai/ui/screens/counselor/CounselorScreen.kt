package com.example.campusai.ui.screens.counselor

import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
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
import com.example.campusai.data.model.ChatMessage
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun CounselorScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val scope = rememberCoroutineScope()

    var messages by remember {
        mutableStateOf(
            listOf(
                ChatMessage(
                    "assistant",
                    "你好，我是 AI 导员小夏。你可以问我课程流程、奖助政策、校园服务等问题。当前回答来自 Mock 知识库，仅供演示参考。"
                )
            )
        )
    }
    var inputText by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .graphicsLayer { alpha = animatedAlpha }
    ) {
        LazyColumn(
            modifier = Modifier
                .weight(1f)
                .padding(horizontal = 20.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 16.dp)
        ) {
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text("AI 导员", style = MaterialTheme.typography.headlineMedium)
                        Text("基于校园知识库的事务问答，当前能力会明确标注 Mock。", color = Muted, fontSize = 13.sp)
                    }
                    ModeBadge(mockMode)
                }
                Spacer(Modifier.height(14.dp))
            }

            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(Surface)
                        .border(1.dp, Line, RoundedCornerShape(10.dp))
                        .padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(RoundedCornerShape(13.dp))
                            .background(RobotAvatarBg),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.size(28.dp))
                    }
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("AI 导员小夏", fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                            MockBadge()
                        }
                        Text("校园事务问答 · 不替代学校正式通知", color = Muted, fontSize = 11.sp)
                    }
                }
                Spacer(Modifier.height(8.dp))
            }

            items(messages) { msg ->
                ChatBubble(msg)
            }

            if (sending) {
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth(0.76f)
                            .clip(RoundedCornerShape(9.dp))
                            .background(ChatAssistantBg)
                            .padding(12.dp, 14.dp)
                    ) {
                        Text("正在查找校园知识库…", fontSize = 13.sp, color = Muted)
                    }
                }
            }
        }

        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Surface)
                .border(1.dp, Line)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                listOf("奖学金申请条件有哪些？", "如何办理课程重修？", "校园卡挂失后怎么补办？").forEach { q ->
                    OutlinedButton(
                        onClick = { inputText = q },
                        shape = RoundedCornerShape(8.dp),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary)
                    ) {
                        Text(q, fontSize = 11.sp, maxLines = 1)
                    }
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = inputText,
                    onValueChange = { inputText = it },
                    placeholder = { Text("输入你的校园事务问题…") },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(8.dp),
                    maxLines = 3,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = InputBorder
                    )
                )
                IconButton(
                    onClick = {
                        val text = inputText.trim()
                        if (text.isEmpty() || sending) return@IconButton
                        scope.launch {
                            messages = messages + ChatMessage("user", text)
                            inputText = ""
                            sending = true
                            try {
                                val answer = repository.chat(text)
                                messages = messages + ChatMessage("assistant", answer)
                            } catch (_: Exception) {
                                messages = messages + ChatMessage("assistant", "暂时无法连接知识库，请检查网络后重试。")
                            } finally {
                                sending = false
                            }
                        }
                    },
                    enabled = !sending && inputText.isNotBlank(),
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (!sending && inputText.isNotBlank()) Primary else Primary.copy(alpha = 0.3f))
                ) {
                    Icon(Icons.Default.Send, "发送", tint = Surface, modifier = Modifier.size(20.dp))
                }
            }

            Row(
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                Icon(Icons.Default.Shield, null, tint = Success, modifier = Modifier.size(14.dp))
                Text("回答仅提供校园事务辅助，不进行心理或疾病诊断。", color = Muted, fontSize = 10.sp)
            }
            Spacer(Modifier.height(8.dp))
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size + 2)
        }
    }
}

@Composable
private fun ChatBubble(msg: ChatMessage) {
    val isUser = msg.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
    ) {
        Column(
            modifier = Modifier
                .widthIn(max = 280.dp)
                .clip(RoundedCornerShape(9.dp))
                .background(if (isUser) ChatUserBg else ChatAssistantBg)
                .padding(12.dp, 14.dp)
        ) {
            Text(msg.text, fontSize = 13.sp, lineHeight = 20.sp, color = TextPrimary)
        }
    }
}


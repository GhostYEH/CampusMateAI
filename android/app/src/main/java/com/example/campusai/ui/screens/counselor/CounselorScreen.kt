package com.example.campusai.ui.screens.counselor

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.ChatMessage
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.MockBadge
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.components.TypingIndicator
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.components.slideInAnimation
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private val AiBlue = Color(0xFF5368E8)
private val AiBlueDeep = Color(0xFF3449C7)
private val AiOrange = Color(0xFFFFA43A)

@Composable
fun CounselorScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var messages by remember {
        mutableStateOf(
            listOf(
                ChatMessage(
                    "assistant",
                    "你好，我是 AI 导员小夏。课程流程、奖助政策、校园服务，都可以来问我。当前回答来自 Mock 知识库，仅供演示参考。",
                ),
            ),
        )
    }

    fun sendMessage(text: String) {
        val question = text.trim()
        if (question.isEmpty() || sending) return
        scope.launch {
            messages = messages + ChatMessage("user", question)
            input = ""
            sending = true
            error = null
            try {
                messages = messages + ChatMessage("assistant", repository.chat(question))
            } catch (_: Exception) {
                error = "暂时无法连接校园知识库，请检查网络后重试。"
            } finally {
                sending = false
            }
        }
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        LazyColumn(
            modifier = Modifier.weight(1f),
            state = listState,
            contentPadding = PaddingValues(16.dp, 12.dp, 16.dp, 18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { CounselorHeader(mockMode) }
            item { CounselorHero(reduceMotion) }
            item {
                Text("你可以这样问", fontSize = 14.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(9.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(
                        listOf(
                            "奖学金申请需要什么材料？",
                            "课程重修怎么办理？",
                            "校园卡丢了怎么补办？",
                        ),
                    ) { question ->
                        SuggestionChip(
                            onClick = { sendMessage(question) },
                            label = { Text(question, maxLines = 1) },
                            icon = { Icon(Icons.Default.AutoAwesome, null, Modifier.size(16.dp)) },
                            shape = RoundedCornerShape(12.dp),
                            colors = SuggestionChipDefaults.suggestionChipColors(
                                containerColor = Surface,
                                labelColor = TextPrimary,
                                iconContentColor = AiBlue,
                            ),
                            border = SuggestionChipDefaults.suggestionChipBorder(
                                enabled = true,
                                borderColor = Line,
                            ),
                        )
                    }
                }
            }
            items(messages) { message ->
                ChatBubble(message, reduceMotion)
            }
            if (sending) {
                item { TypingBubble() }
            }
            error?.let { message ->
                item {
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp))
                            .background(AlertErrorBg).padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Icon(Icons.Default.CloudOff, null, tint = AlertErrorText, modifier = Modifier.size(18.dp))
                        Text(message, color = AlertErrorText, fontSize = 12.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { error = null }) { Text("知道了") }
                    }
                }
            }
        }
        ChatComposer(
            value = input,
            sending = sending,
            onValueChange = { input = it },
            onSend = { sendMessage(input) },
        )
    }

    LaunchedEffect(messages.size, sending) {
        if (!reduceMotion && messages.isNotEmpty()) {
            listState.animateScrollToItem(listState.layoutInfo.totalItemsCount.coerceAtLeast(1) - 1)
        }
    }
}

@Composable
private fun CounselorHeader(mockMode: Boolean) {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("AI 导员", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Text("校园问题，随时来聊一聊", color = Muted, fontSize = 13.sp)
        }
        ModeBadge(mockMode)
    }
}

@Composable
private fun CounselorHero(reduceMotion: Boolean) {
    Box(
        Modifier.fillMaxWidth().height(146.dp).clip(RoundedCornerShape(26.dp))
            .background(Brush.linearGradient(listOf(AiBlue, AiBlueDeep)))
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            Modifier.size(150.dp).offset(x = 250.dp, y = (-54).dp).clip(CircleShape)
                .background(Color.White.copy(alpha = .08f)),
        )
        Row(
            Modifier.fillMaxSize().padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(15.dp),
        ) {
            Box(
                Modifier.size(58.dp).clip(RoundedCornerShape(19.dp)).background(Color.White.copy(alpha = .16f)),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Default.SmartToy, null, tint = Color.White, modifier = Modifier.size(32.dp)) }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("导员小夏", color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Bold)
                    MockBadge()
                }
                Text("我会结合校园知识库帮你整理流程与材料", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    Box(Modifier.size(7.dp).clip(CircleShape).background(Color(0xFF67E4BC)))
                    Text("在线 · 通常很快回复", color = Color.White.copy(alpha = .82f), fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
private fun ChatBubble(message: ChatMessage, reduceMotion: Boolean) {
    val isUser = message.role == "user"
    Row(
        Modifier.fillMaxWidth().slideInAnimation(fromLeft = !isUser, enabled = !reduceMotion),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Bottom,
    ) {
        if (!isUser) {
            Box(
                Modifier.size(30.dp).clip(RoundedCornerShape(10.dp)).background(RobotAvatarBg),
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.size(17.dp)) }
            Spacer(Modifier.width(7.dp))
        }
        Column(
            Modifier.widthIn(max = 292.dp).clip(
                if (isUser) RoundedCornerShape(19.dp, 19.dp, 5.dp, 19.dp)
                else RoundedCornerShape(19.dp, 19.dp, 19.dp, 5.dp),
            ).background(if (isUser) AiBlue else Surface)
                .then(if (isUser) Modifier else Modifier.border(1.dp, Line, RoundedCornerShape(19.dp)))
                .padding(horizontal = 14.dp, vertical = 12.dp),
        ) {
            Text(
                message.text,
                color = if (isUser) Color.White else TextPrimary,
                fontSize = 13.sp,
                lineHeight = 20.sp,
            )
            if (!isUser) {
                Spacer(Modifier.height(7.dp))
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Icon(Icons.Default.MenuBook, null, tint = Muted, modifier = Modifier.size(12.dp))
                    Text("Mock 校园知识库", color = Muted, fontSize = 9.sp)
                }
            }
        }
    }
}

@Composable
private fun TypingBubble() {
    Row(verticalAlignment = Alignment.Bottom) {
        Box(
            Modifier.size(30.dp).clip(RoundedCornerShape(10.dp)).background(RobotAvatarBg),
            contentAlignment = Alignment.Center,
        ) { Icon(Icons.Default.SmartToy, null, tint = Primary, modifier = Modifier.size(17.dp)) }
        Spacer(Modifier.width(7.dp))
        Row(
            Modifier.clip(RoundedCornerShape(19.dp, 19.dp, 19.dp, 5.dp)).background(Surface)
                .border(1.dp, Line, RoundedCornerShape(19.dp)).padding(horizontal = 14.dp, vertical = 13.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(9.dp),
        ) {
            TypingIndicator(dotColor = AiBlue)
            Text("正在查找校园知识库", color = Muted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun ChatComposer(
    value: String,
    sending: Boolean,
    onValueChange: (String) -> Unit,
    onSend: () -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().background(Surface).border(1.dp, Line)
            .navigationBarsPadding().imePadding().padding(12.dp, 10.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("输入你的校园事务问题…", fontSize = 13.sp) },
                maxLines = 4,
                shape = RoundedCornerShape(16.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary,
                    unfocusedBorderColor = InputBorder,
                ),
            )
            FilledIconButton(
                onClick = onSend,
                enabled = value.isNotBlank() && !sending,
                modifier = Modifier.size(50.dp),
                shape = RoundedCornerShape(16.dp),
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = AiBlue,
                    contentColor = Color.White,
                ),
            ) { Icon(if (sending) Icons.Default.HourglassTop else Icons.Default.Send, "发送") }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            Icon(Icons.Default.Shield, null, tint = Success, modifier = Modifier.size(13.dp))
            Text("仅提供校园事务辅助，不替代学校正式通知或专业咨询", color = Muted, fontSize = 9.sp)
        }
    }
}

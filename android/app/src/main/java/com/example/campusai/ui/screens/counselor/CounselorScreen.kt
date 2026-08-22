package com.example.campusai.ui.screens.counselor

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.ChatMessage
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.TypingIndicator
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.components.slideInAnimation
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private data class QuickQuestion(
    val label: String,
    val prompt: String,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
)

@Composable
fun CounselorScreen(repository: AppRepository, initialPrompt: String? = null) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    var input by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var messages by remember(mockMode) {
        mutableStateOf(listOf(ChatMessage("assistant", "你好，我是 AI 校园助手小灵。课程流程、奖助政策、校园服务，都可以来问我。\n\n我会结合校园知识库与后端配置给你整理清晰步骤。")))
    }

    fun sendMessage(text: String) {
        val question = text.trim()
        if (question.isEmpty() || sending) return
        scope.launch {
            messages += ChatMessage("user", question)
            input = ""
            sending = true
            error = null
            try {
                messages += ChatMessage("assistant", "")
                var receivedChunk = false
                repository.streamChat(question) { chunk ->
                    receivedChunk = true
                    messages.lastOrNull()?.takeIf { it.role == "assistant" }?.let { last ->
                        messages = messages.dropLast(1) + last.copy(text = last.text + chunk)
                    }
                }
                if (!receivedChunk) throw IllegalStateException("empty AI stream")
            } catch (_: Exception) {
                error = "暂时无法连接校园知识库，请检查网络后重试。"
                messages = messages.dropLastWhile { it.role == "assistant" && it.text.isEmpty() }
            } finally {
                sending = false
            }
        }
    }

    LaunchedEffect(initialPrompt) { initialPrompt?.takeIf { it.isNotBlank() }?.let(::sendMessage) }
    LaunchedEffect(messages.size, sending) {
        if (!reduceMotion && messages.isNotEmpty()) {
            listState.animateScrollToItem((listState.layoutInfo.totalItemsCount - 1).coerceAtLeast(0))
        }
    }

    Column(
        Modifier
            .fillMaxSize()
            .background(Background)
            .padding(
                bottom = floatingDockContentBottomPadding(
                    WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
                ),
            ),
    ) {
        LazyColumn(
            modifier = Modifier.weight(1f),
            state = listState,
            contentPadding = PaddingValues(16.dp, 16.dp, 16.dp, 14.dp),
            verticalArrangement = Arrangement.spacedBy(13.dp),
        ) {
            item { AssistantHeader(mockMode) }
            item { AssistantHero(mockMode, reduceMotion) }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    Text("你可以这样问", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
                    QuickQuestionGrid(onAsk = ::sendMessage)
                }
            }
            items(messages) { message -> AssistantBubble(message, reduceMotion) }
            if (sending) item { LoadingBubble(reduceMotion) }
            error?.let { message -> item { ErrorNotice(message) { error = null } } }
        }
        AssistantComposer(input, sending, { input = it }) { sendMessage(input) }
    }
}

@Composable
private fun AssistantHeader(mockMode: Boolean) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("AI 校园助手", color = TextPrimary, fontSize = 27.sp, fontWeight = FontWeight.ExtraBold)
                Text("✦", color = Primary, fontSize = 22.sp, modifier = Modifier.padding(start = 4.dp, bottom = 14.dp))
            }
            Text("校园问题，随时来聊一聊", color = Muted, fontSize = 14.sp)
        }
        Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(if (mockMode) Accent else Color(0xFFFF9646)))
            Text(if (mockMode) " 演示模式" else " 真实后端", color = TextPrimary, fontSize = 12.sp)
        }
    }
}

@Composable
private fun AssistantHero(mockMode: Boolean, reduceMotion: Boolean) {
    Box(
        Modifier.fillMaxWidth().height(144.dp).clip(RoundedCornerShape(25.dp))
            .background(Brush.linearGradient(listOf(Color(0xFFF9FAFF), Color(0xFFF1F2FF), Color.White)))
            .border(1.dp, Color(0xFFE1E5FF), RoundedCornerShape(25.dp)).enterAnimation(enabled = !reduceMotion),
    ) {
        Image(
            painterResource(R.drawable.ai_campus_robot), null,
            Modifier.size(124.dp).align(Alignment.CenterStart).padding(start = 3.dp), contentScale = ContentScale.Fit,
        )
        Column(
            Modifier.fillMaxWidth().padding(start = 125.dp, top = 25.dp, end = 13.dp),
            verticalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("校园事务助手", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1)
                Box(Modifier.size(6.dp).clip(CircleShape).background(if (mockMode) Accent else Color(0xFFFF9646)))
                Text(if (mockMode) "演示" else "真实后端", color = TextPrimary, fontSize = 10.sp)
            }
            Text("帮你整理流程、材料和下一步", color = Muted, fontSize = 12.sp, lineHeight = 17.sp, maxLines = 1)
            Row(
                Modifier.clip(RoundedCornerShape(15.dp)).background(Color(0xFFF0F1FF)).padding(horizontal = 7.dp, vertical = 5.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.VerifiedUser, null, tint = Primary, modifier = Modifier.size(13.dp))
                Text(" 覆盖奖助、课程、校园服务问答", color = Primary, fontSize = 9.sp, maxLines = 1)
            }
        }
    }
}

@Composable
private fun QuickQuestionGrid(onAsk: (String) -> Unit) {
    val questions = listOf(
        QuickQuestion("奖学金申请\n材料清单", "奖学金申请需要什么材料？", Icons.Default.School),
        QuickQuestion("课程重修\n办理流程", "课程重修怎么办理？", Icons.Default.MenuBook),
        QuickQuestion("校园卡丢失\n补办地点", "校园卡丢失去哪里补办？", Icons.Default.CreditCard),
        QuickQuestion("请假流程\n怎么走", "请假流程怎么走？", Icons.Default.EventAvailable),
    )
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        questions.chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { question ->
                    Row(
                        Modifier.weight(1f).heightIn(min = 88.dp).clip(RoundedCornerShape(18.dp)).background(Surface)
                            .border(1.dp, Line, RoundedCornerShape(18.dp)).clickable { onAsk(question.prompt) }.padding(11.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(Modifier.size(40.dp).clip(RoundedCornerShape(13.dp)).background(PrimarySoft), contentAlignment = Alignment.Center) {
                            Icon(question.icon, null, tint = Primary, modifier = Modifier.size(21.dp))
                        }
                        Text(question.label, Modifier.padding(start = 9.dp).weight(1f), color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium, lineHeight = 18.sp)
                        Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(18.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun AssistantBubble(message: ChatMessage, reduceMotion: Boolean) {
    val assistant = message.role == "assistant"
    Row(
        Modifier.fillMaxWidth().slideInAnimation(fromLeft = assistant, enabled = !reduceMotion),
        horizontalArrangement = if (assistant) Arrangement.Start else Arrangement.End,
        verticalAlignment = Alignment.Bottom,
    ) {
        if (assistant) {
            Image(painterResource(R.drawable.ai_campus_robot), null, Modifier.size(46.dp).padding(end = 6.dp), contentScale = ContentScale.Fit)
        }
        Column(
            Modifier.widthIn(max = 300.dp)
                .clip(if (assistant) RoundedCornerShape(22.dp, 22.dp, 22.dp, 5.dp) else RoundedCornerShape(22.dp, 22.dp, 5.dp, 22.dp))
                .background(if (assistant) Surface else Primary)
                .then(if (assistant) Modifier.border(1.dp, Line, RoundedCornerShape(22.dp)) else Modifier)
                .padding(14.dp),
        ) {
            MarkdownMessage(message.text, color = if (assistant) TextPrimary else Color.White)
            if (assistant && message.text.isNotBlank()) {
                Row(Modifier.padding(top = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.MenuBook, null, tint = Muted, modifier = Modifier.size(13.dp))
                    Text("  校友知识库 · 流程同步", color = Muted, fontSize = 11.sp)
                }
            }
        }
    }
}

@Composable
private fun LoadingBubble(reduceMotion: Boolean) = Row(verticalAlignment = Alignment.Bottom) {
    Image(painterResource(R.drawable.ai_campus_robot), null, Modifier.size(40.dp).padding(end = 6.dp), contentScale = ContentScale.Fit)
    Row(
        Modifier.clip(RoundedCornerShape(18.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(18.dp)).padding(11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TypingIndicator(dotColor = Primary, enabled = !reduceMotion)
        Text(" 正在查询校园知识库", color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun ErrorNotice(message: String, dismiss: () -> Unit) = Row(
    Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(AlertErrorBg).padding(12.dp),
    verticalAlignment = Alignment.CenterVertically,
) {
    Icon(Icons.Default.CloudOff, null, tint = AlertErrorText)
    Text(message, Modifier.weight(1f).padding(start = 8.dp), color = AlertErrorText, fontSize = 13.sp)
    TextButton(dismiss) { Text("知道了") }
}

@Composable
private fun AssistantComposer(value: String, sending: Boolean, onValueChange: (String) -> Unit, onSend: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)).background(Surface)
            .border(1.dp, Line, RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp)).imePadding().padding(11.dp),
        verticalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value, onValueChange, Modifier.weight(1f),
                placeholder = { Text("✦ 输入你的校园事务问题…", color = Muted, fontSize = 14.sp) }, maxLines = 2,
                shape = RoundedCornerShape(19.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = Primary, unfocusedBorderColor = Primary.copy(alpha = .4f),
                    focusedContainerColor = Surface, unfocusedContainerColor = Surface, cursorColor = Primary,
                ),
            )
            FilledIconButton(
                onClick = onSend, enabled = value.isNotBlank() && !sending, modifier = Modifier.size(52.dp), shape = RoundedCornerShape(19.dp),
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = Primary, contentColor = Color.White, disabledContainerColor = PrimarySoft),
            ) { Icon(if (sending) Icons.Default.HourglassTop else Icons.Default.Send, "发送", Modifier.size(22.dp)) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Shield, null, tint = Success, modifier = Modifier.size(13.dp))
            Text(" 仅提供校园事务辅助，不替代学校正式通知或专业咨询", color = Muted, fontSize = 10.sp, maxLines = 1)
        }
    }
}

@Composable
private fun MarkdownMessage(markdown: String, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        markdown.replace("\r\n", "\n").lines().forEach { rawLine ->
            val line = rawLine.trimEnd()
            when {
                line.startsWith("### ") || line.startsWith("## ") || line.startsWith("# ") ->
                    MarkdownText(line.substringAfter(' ').trim(), color, 16.sp, 22.sp, FontWeight.Bold)
                line.startsWith("- ") || line.startsWith("* ") -> Row(verticalAlignment = Alignment.Top) {
                    Text("•", color = Primary, fontSize = 14.sp, modifier = Modifier.padding(end = 6.dp))
                    MarkdownText(line.drop(2), color, 14.sp, 21.sp, FontWeight.Normal, Modifier.weight(1f))
                }
                Regex("^\\d+[.)]\\s+").containsMatchIn(line) -> MarkdownText(line, color, 14.sp, 21.sp, FontWeight.Normal)
                else -> MarkdownText(line, color, 14.sp, 21.sp, FontWeight.Normal)
            }
        }
    }
}

@Composable
private fun MarkdownText(
    text: String,
    color: Color,
    fontSize: TextUnit,
    lineHeight: TextUnit,
    fontWeight: FontWeight,
    modifier: Modifier = Modifier,
) {
    val annotated: AnnotatedString = buildAnnotatedString {
        var cursor = 0
        while (cursor < text.length) {
            val start = text.indexOf("**", cursor)
            if (start < 0) {
                append(text.substring(cursor))
                break
            }
            append(text.substring(cursor, start))
            val end = text.indexOf("**", start + 2)
            if (end < 0) {
                append(text.substring(start))
                break
            }
            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(text.substring(start + 2, end)) }
            cursor = end + 2
        }
    }
    Text(annotated, modifier = modifier, color = color, fontSize = fontSize, lineHeight = lineHeight, fontWeight = fontWeight)
}

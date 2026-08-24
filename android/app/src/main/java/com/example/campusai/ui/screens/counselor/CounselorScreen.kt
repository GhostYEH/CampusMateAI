package com.example.campusai.ui.screens.counselor

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
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
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.BuildConfig
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.yield

private val CpmBlue = Color(0xFF385AF6)
private val CpmViolet = Color(0xFF8152F6)
private val CpmLine = Color(0xFFDDE3FA)

@Composable
fun CounselorScreen(repository: AppRepository, initialPrompt: String? = null) {
    val factory = remember(repository) { CounselorViewModelFactory(repository) }
    val viewModel: CounselorViewModel = viewModel(factory = factory)
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val accessToken by repository.accessToken.collectAsStateWithLifecycle()

    LaunchedEffect(initialPrompt) { initialPrompt?.takeIf(String::isNotBlank)?.let(viewModel::send) }
    CpmCounselorContent(
        state = state,
        reduceMotion = reduceMotion,
        accessToken = accessToken.orEmpty(),
        onInputChange = viewModel::updateInput,
        onSend = viewModel::send,
        onAsk = viewModel::send,
        onShuffle = viewModel::shuffleRecommendations,
        onRetry = viewModel::retryLast,
        onPlayback = viewModel::sendPlaybackCommand,
    )
}

@Composable
private fun CpmCounselorContent(
    state: CpmCounselorUiState,
    reduceMotion: Boolean,
    accessToken: String,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onAsk: (String) -> Unit,
    onShuffle: () -> Unit,
    onRetry: () -> Unit,
    onPlayback: (DigitalHumanCommand) -> Unit,
) {
    val listState = rememberLazyListState()
    LaunchedEffect(state.messages.size, state.messages.lastOrNull()?.content?.length) {
        if (state.chatActive) {
            yield()
            val last = listState.layoutInfo.totalItemsCount - 1
            if (last >= 0) {
                if (reduceMotion) listState.scrollToItem(last) else listState.animateScrollToItem(last)
            }
        }
    }

    Box(
        Modifier.fillMaxSize()
            .background(Brush.verticalGradient(listOf(Color(0xFFFBFCFF), Color(0xFFF0F2FF))))
            .padding(bottom = floatingDockContentBottomPadding(
                WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
            )),
    ) {
        Column(Modifier.align(Alignment.TopCenter).fillMaxSize().widthIn(max = 760.dp)) {
            LazyColumn(
                modifier = Modifier.weight(1f),
                state = listState,
                contentPadding = PaddingValues(18.dp, 18.dp, 18.dp, 16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                item("brand") {
                    AnimatedVisibility(
                        visible = !state.chatActive,
                        enter = fadeIn(),
                        exit = fadeOut(tween(if (reduceMotion) 0 else 180)) + shrinkVertically(),
                    ) { CpmHeader() }
                }
                item("digital-human") {
                    CpmDigitalHumanCard(state, accessToken, reduceMotion, onPlayback)
                }
                item("recommendations") {
                    AnimatedVisibility(
                        visible = !state.chatActive,
                        enter = fadeIn() + slideInVertically { it / 4 },
                        exit = fadeOut(tween(if (reduceMotion) 0 else 190)) + slideOutVertically { -it / 5 } + shrinkVertically(),
                    ) { CpmRecommendations(state.recommendations, onAsk, onShuffle) }
                }
                items(state.messages, key = CpmChatMessage::id) { message ->
                    CpmMessageBubble(message, state.sending, onRetry)
                }
                item("tail") { Spacer(Modifier.height(2.dp)) }
            }
            CpmComposer(state.input, state.sending, onInputChange, onSend)
        }
    }
}

@Composable
private fun CpmHeader() = Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
    Row(verticalAlignment = Alignment.Top) {
        Text("CPM", color = TextPrimary, fontSize = 38.sp, fontWeight = FontWeight.Black)
        Text("✦", color = CpmBlue, fontSize = 24.sp, modifier = Modifier.padding(start = 7.dp, top = 1.dp))
    }
    Text("校园问题，随时来聊一聊", color = Muted, fontSize = 16.sp, fontWeight = FontWeight.Medium)
}

@Composable
private fun CpmDigitalHumanCard(
    state: CpmCounselorUiState,
    accessToken: String,
    reduceMotion: Boolean,
    onPlayback: (DigitalHumanCommand) -> Unit,
) {
    val compact = state.chatActive
    val duration = if (reduceMotion) 0 else 280
    val cardHeight by animateDpAsState(if (compact) 78.dp else 236.dp, tween(duration), label = "cardHeight")
    val avatarSize by animateDpAsState(if (compact) 58.dp else 166.dp, tween(duration), label = "avatarSize")
    val cardRadius by animateDpAsState(if (compact) 24.dp else 31.dp, tween(duration), label = "cardRadius")
    BoxWithConstraints(
        Modifier.fillMaxWidth().height(cardHeight)
            .shadow(20.dp, RoundedCornerShape(cardRadius), ambientColor = Color(0x1A4B5DAC), spotColor = Color(0x144B5DAC))
            .clip(RoundedCornerShape(cardRadius))
            .background(Brush.linearGradient(listOf(Color(0xF8FFFFFF), Color(0xFFF2F2FF), Color(0xF8FFFFFF))))
            .border(1.dp, Color.White, RoundedCornerShape(cardRadius)),
    ) {
        Row(
            Modifier.fillMaxSize().padding(if (compact) 10.dp else 18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(if (compact) 12.dp else 18.dp),
        ) {
            Box(
                Modifier.size(avatarSize).graphicsLayer { shape = CircleShape; clip = true }
                    .background(Brush.radialGradient(listOf(Color.White, Color(0xFFE3E7FF))))
                    .border(2.dp, Color.White, CircleShape),
            ) {
                DigitalHumanStage(
                    apiBaseUrl = BuildConfig.API_BASE_URL,
                    accessToken = accessToken,
                    speechText = state.speechText,
                    speechRequestId = state.speechRequestId,
                    command = state.playbackCommand,
                    commandRequestId = state.playbackCommandId,
                )
            }
            if (compact) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("你好，我是CPM", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
                    Text(if (state.sending) "正在生成回答…" else "尽管提问！", color = if (state.sending) CpmBlue else Muted, fontSize = 12.sp)
                }
                CpmMiniControl(Icons.Default.VolumeOff, "静音") { onPlayback(DigitalHumanCommand.TOGGLE_MUTE) }
                CpmMiniControl(Icons.Default.PauseCircleOutline, "暂停") { onPlayback(DigitalHumanCommand.TOGGLE_PAUSE) }
            } else {
                Column(Modifier.weight(1f).fillMaxHeight(), verticalArrangement = Arrangement.Center) {
                    Text(
                        "你好，我是CPM",
                        style = TextStyle(
                            brush = Brush.horizontalGradient(listOf(CpmBlue, CpmViolet)),
                            fontSize = 23.sp,
                            fontWeight = FontWeight.Black,
                        ),
                        maxLines = 1,
                    )
                    Text("尽管提问！", color = Muted, fontSize = 15.sp, modifier = Modifier.padding(top = 8.dp, bottom = 18.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        CpmControl(Icons.Default.VolumeOff, "静音", Modifier.weight(1f)) { onPlayback(DigitalHumanCommand.TOGGLE_MUTE) }
                        CpmControl(Icons.Default.PauseCircleOutline, "暂停", Modifier.weight(1f)) { onPlayback(DigitalHumanCommand.TOGGLE_PAUSE) }
                        CpmControl(Icons.Default.Replay, "重播", Modifier.weight(1f)) { onPlayback(DigitalHumanCommand.REPLAY) }
                    }
                }
            }
        }
    }
}

@Composable
private fun CpmControl(icon: ImageVector, label: String, modifier: Modifier, onClick: () -> Unit) {
    Column(
        modifier.height(72.dp).clip(RoundedCornerShape(18.dp)).background(Color(0xA6FFFFFF))
            .border(1.dp, CpmLine, RoundedCornerShape(18.dp)).clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, label, tint = CpmBlue, modifier = Modifier.size(25.dp))
        Text(label, color = Color(0xFF596785), fontSize = 12.sp, modifier = Modifier.padding(top = 5.dp))
    }
}

@Composable
private fun CpmMiniControl(icon: ImageVector, label: String, onClick: () -> Unit) = FilledIconButton(
    onClick = onClick,
    modifier = Modifier.size(38.dp),
    colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color.White, contentColor = CpmBlue),
) { Icon(icon, label, Modifier.size(20.dp)) }

@Composable
private fun CpmRecommendations(questions: List<CpmPrompt>, onAsk: (String) -> Unit, onShuffle: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("你可以这样问", color = TextPrimary, fontSize = 21.sp, fontWeight = FontWeight.Black)
            Text("✦", color = CpmViolet, fontSize = 16.sp, modifier = Modifier.padding(start = 5.dp, bottom = 7.dp))
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onShuffle) {
                Text("换一批", color = Muted, fontSize = 13.sp)
                Icon(Icons.Default.Refresh, null, tint = Muted, modifier = Modifier.padding(start = 4.dp).size(17.dp))
            }
        }
        questions.chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                row.forEach { question ->
                    Row(
                        Modifier.weight(1f).heightIn(min = 88.dp)
                            .shadow(10.dp, RoundedCornerShape(22.dp), ambientColor = Color(0x0F41518C), spotColor = Color(0x0F41518C))
                            .clip(RoundedCornerShape(22.dp)).background(Color(0xEFFFFFFF))
                            .border(1.dp, CpmLine, RoundedCornerShape(22.dp)).clickable { onAsk(question.prompt) }.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(Modifier.size(44.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) {
                            Icon(question.icon, null, tint = CpmBlue, modifier = Modifier.size(23.dp))
                        }
                        Text(question.label, Modifier.padding(start = 10.dp).weight(1f), color = TextPrimary, fontSize = 13.sp, lineHeight = 19.sp, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun CpmMessageBubble(message: CpmChatMessage, sending: Boolean, onRetry: () -> Unit) {
    val assistant = message.role == "assistant"
    val clipboard = LocalClipboardManager.current
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (assistant) Arrangement.Start else Arrangement.End, verticalAlignment = Alignment.Bottom) {
        if (assistant) CpmAvatarBadge()
        Column(
            Modifier.widthIn(max = 330.dp).then(
                if (assistant) Modifier.shadow(9.dp, RoundedCornerShape(22.dp), ambientColor = Color(0x12404E7D), spotColor = Color(0x10404E7D))
                    .background(Color(0xF8FFFFFF), RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp))
                    .border(1.dp, CpmLine, RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp))
                else Modifier.background(Brush.linearGradient(listOf(CpmBlue, CpmViolet)), RoundedCornerShape(22.dp, 22.dp, 6.dp, 22.dp))
            ).padding(horizontal = 15.dp, vertical = 13.dp),
        ) {
            if (assistant && message.status == CpmMessageStatus.GENERATING && message.content.isEmpty()) CpmThinkingText()
            else {
                MarkdownMessage(message.content, if (assistant) TextPrimary else Color.White)
                if (assistant && message.status == CpmMessageStatus.GENERATING) CpmStreamingCursor()
            }
            if (assistant && message.status == CpmMessageStatus.ERROR) {
                Text(message.errorMessage ?: "生成中断", color = AlertErrorText, fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp))
                TextButton(onClick = onRetry, contentPadding = PaddingValues(0.dp)) { Text("重新生成", color = CpmBlue, fontSize = 12.sp) }
            }
            if (assistant && message.status == CpmMessageStatus.COMPLETED && message.content.isNotBlank()) {
                Row(Modifier.padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { clipboard.setText(AnnotatedString(message.content)) }, contentPadding = PaddingValues(horizontal = 4.dp)) {
                        Icon(Icons.Default.ContentCopy, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" 复制", color = Muted, fontSize = 11.sp)
                    }
                    TextButton(onClick = onRetry, contentPadding = PaddingValues(horizontal = 4.dp), enabled = !sending) {
                        Icon(Icons.Default.Refresh, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" 重新生成", color = Muted, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun CpmAvatarBadge() = Box(
    Modifier.padding(end = 7.dp).size(32.dp).clip(CircleShape).background(PrimarySoft).border(1.dp, Color.White, CircleShape),
    contentAlignment = Alignment.Center,
) { Text("CPM", color = CpmBlue, fontSize = 8.sp, fontWeight = FontWeight.Black) }

@Composable
private fun CpmThinkingText() {
    val transition = rememberInfiniteTransition(label = "thinking")
    val phase by transition.animateFloat(0f, 1f, infiniteRepeatable(tween(900), RepeatMode.Restart), label = "thinkingPhase")
    Text("正在思考" + when { phase < .33f -> "."; phase < .66f -> ".."; else -> "..." }, color = Muted, fontSize = 13.sp)
}

@Composable
private fun CpmStreamingCursor() {
    val transition = rememberInfiniteTransition(label = "cursor")
    val alpha by transition.animateFloat(.2f, 1f, infiniteRepeatable(tween(520), RepeatMode.Reverse), label = "cursorAlpha")
    Box(Modifier.padding(top = 5.dp).width(2.dp).height(16.dp).background(CpmBlue.copy(alpha = alpha)))
}

@Composable
private fun CpmComposer(value: String, sending: Boolean, onValueChange: (String) -> Unit, onSend: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().background(Color(0xEFFFFFFF), RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp))
            .border(1.dp, Color.White, RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)).imePadding().padding(horizontal = 14.dp, vertical = 11.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedTextField(
                value, onValueChange, Modifier.weight(1f),
                placeholder = { Text("✦ 输入你想聊的问题…", color = Muted, fontSize = 14.sp) }, maxLines = 3, shape = RoundedCornerShape(22.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CpmBlue, unfocusedBorderColor = CpmLine,
                    focusedContainerColor = Color.White, unfocusedContainerColor = Color(0xEFFFFFFF), cursorColor = CpmBlue,
                ),
            )
            FilledIconButton(
                onClick = onSend, enabled = value.isNotBlank() && !sending, modifier = Modifier.size(54.dp), shape = CircleShape,
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = CpmBlue, contentColor = Color.White, disabledContainerColor = PrimarySoft),
            ) { Icon(Icons.AutoMirrored.Filled.Send, "发送", Modifier.size(23.dp)) }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Shield, null, tint = Muted, modifier = Modifier.size(13.dp))
            Text(" 仅提供成长建议，不替代学校正式通知或专业咨询", color = Muted, fontSize = 10.sp, maxLines = 1)
        }
    }
}

@Composable
private fun MarkdownMessage(markdown: String, color: Color) = Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
    markdown.replace("\r\n", "\n").lines().forEach { rawLine ->
        val line = rawLine.trimEnd()
        when {
            line.startsWith("### ") || line.startsWith("## ") || line.startsWith("# ") -> MarkdownText(line.substringAfter(' ').trim(), color, 16.sp, 22.sp, FontWeight.Bold)
            line.startsWith("- ") || line.startsWith("* ") -> Row(verticalAlignment = Alignment.Top) {
                Text("•", color = if (color == Color.White) Color.White else Primary, fontSize = 14.sp, modifier = Modifier.padding(end = 6.dp))
                MarkdownText(line.drop(2), color, 14.sp, 21.sp, FontWeight.Normal, Modifier.weight(1f))
            }
            else -> MarkdownText(line, color, 14.sp, 21.sp, FontWeight.Normal)
        }
    }
}

@Composable
private fun MarkdownText(text: String, color: Color, fontSize: TextUnit, lineHeight: TextUnit, fontWeight: FontWeight, modifier: Modifier = Modifier) {
    val annotated = buildAnnotatedString {
        var cursor = 0
        while (cursor < text.length) {
            val start = text.indexOf("**", cursor)
            if (start < 0) { append(text.substring(cursor)); break }
            append(text.substring(cursor, start))
            val end = text.indexOf("**", start + 2)
            if (end < 0) { append(text.substring(start)); break }
            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(text.substring(start + 2, end)) }
            cursor = end + 2
        }
    }
    Text(annotated, modifier = modifier, color = color, fontSize = fontSize, lineHeight = lineHeight, fontWeight = fontWeight)
}

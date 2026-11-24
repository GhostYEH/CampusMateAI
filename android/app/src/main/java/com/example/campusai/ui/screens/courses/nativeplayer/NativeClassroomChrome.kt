package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.BorderColor
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.Speed
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineBreak
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.NativeAction
import com.example.campusai.data.classroom.nativeplayer.NativePageState
import com.example.campusai.ui.screens.courses.CampusSceneBackButton
import com.example.campusai.ui.screens.courses.CampusScenePrimaryButton
import com.example.campusai.ui.screens.courses.ClassroomActionShape
import com.example.campusai.ui.screens.courses.ClassroomAmber
import com.example.campusai.ui.screens.courses.ClassroomChalk
import com.example.campusai.ui.screens.courses.ClassroomNight
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.CampusMotion
import com.example.campusai.ui.theme.DarkCampusColors
import com.example.campusai.ui.theme.LightCampusColors
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.LocalCampusColors
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.ProvideCampusIndication
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlin.math.roundToInt

private val BoardColors = DarkCampusColors.copy(
    primary = ClassroomAmber,
    primarySoft = Color(0xFF2D484A),
    accent = Color(0xFFB4D2C3),
    textPrimary = ClassroomChalk,
    muted = Color(0xFFB6C7CB),
    line = Color(0xFF3E535E),
    surface = Color(0xFF192F39),
    background = Color(0xFF101F2B),
)
private val PaperColors = LightCampusColors.copy(
    primary = Color(0xFF27594E),
    primarySoft = Color(0xFFE6EEDD),
    accent = Color(0xFF865526),
    textPrimary = Color(0xFF213832),
    muted = Color(0xFF53685F),
    line = Color(0xFFD7C8AC),
    surface = Color(0xFFFFFBF1),
    background = Color(0xFFF3E7D2),
    dangerText = Color(0xFF9A4032),
    successText = Color(0xFF35694F),
)
private val BoardScheme = darkColorScheme(
    primary = BoardColors.primary,
    onPrimary = ClassroomNight,
    primaryContainer = BoardColors.primarySoft,
    onPrimaryContainer = BoardColors.textPrimary,
    secondary = BoardColors.accent,
    background = BoardColors.background,
    onBackground = BoardColors.textPrimary,
    surface = BoardColors.surface,
    onSurface = BoardColors.textPrimary,
    surfaceVariant = BoardColors.primarySoft,
    onSurfaceVariant = BoardColors.muted,
    outline = BoardColors.line,
    error = BoardColors.dangerText,
)
private val PaperScheme = lightColorScheme(
    primary = PaperColors.primary,
    onPrimary = PaperColors.surface,
    primaryContainer = PaperColors.primarySoft,
    onPrimaryContainer = PaperColors.textPrimary,
    background = PaperColors.background,
    onBackground = PaperColors.textPrimary,
    surface = PaperColors.surface,
    onSurface = PaperColors.textPrimary,
    surfaceVariant = PaperColors.background,
    onSurfaceVariant = PaperColors.muted,
    outline = PaperColors.line,
    error = PaperColors.dangerText,
)

@Composable
internal fun NativeClassroomTheme(paper: Boolean = false, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalCampusColors provides if (paper) PaperColors else BoardColors) {
        MaterialTheme(colorScheme = if (paper) PaperScheme else BoardScheme) {
            ProvideCampusIndication(content)
        }
    }
}

@Composable
internal fun NativeTopBar(
    title: String,
    visited: Int,
    total: Int,
    offline: Boolean,
    showMetrics: Boolean,
    compact: Boolean,
    onClose: () -> Unit,
    onToggleMetrics: () -> Unit,
    controls: @Composable () -> Unit = {},
) {
    Column {
        Row(
            Modifier
                .fillMaxWidth()
                .background(Background.copy(alpha = 0.96f))
                .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
                .padding(horizontal = 4.dp, vertical = if (compact) 0.dp else 5.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CampusSceneBackButton(onBack = onClose, label = "退出课堂")
            Column(Modifier.weight(1f).padding(start = 8.dp, end = 8.dp)) {
                Text(title, color = TextPrimary, fontSize = if (compact) 16.sp else 18.sp, lineHeight = 22.sp,
                    fontWeight = FontWeight.Bold, maxLines = if (compact) 1 else 2, overflow = TextOverflow.Ellipsis)
                if (offline) Text("正在使用缓存", color = Accent, fontSize = 11.sp)
            }
            controls()
            if (total > 0) {
                val badge = RoundedCornerShape(10.dp)
                Row(
                    Modifier.background(PrimarySoft, badge).border(1.dp, Line, badge)
                        .padding(horizontal = 9.dp, vertical = 7.dp),
                    horizontalArrangement = Arrangement.spacedBy(5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Default.Star, contentDescription = null, tint = Primary, modifier = Modifier.size(14.dp))
                    Text("已学 $visited/$total", color = Primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
                }
            }
            IconButton(onClick = onToggleMetrics) {
                Icon(Icons.Default.Speed, contentDescription = if (showMetrics) "隐藏指标" else "显示指标",
                    tint = if (showMetrics) Primary else Muted)
            }
        }
        Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
    }
}

@Composable
internal fun NativeSceneHeading(title: String, type: String, compact: Boolean = false) {
    if (title.isBlank()) return
    val (symbol, category) = when (type) {
        "slide" -> Icons.AutoMirrored.Filled.MenuBook to "知识讲解"
        "pbl" -> Icons.Default.Flag to "项目任务"
        "interactive", "simulation" -> Icons.Default.PlayArrow to "课堂互动"
        else -> Icons.AutoMirrored.Filled.MenuBook to "课件"
    }
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        val shape = RoundedCornerShape(12.dp)
        Box(
            Modifier.size(if (compact) 34.dp else 42.dp).background(Surface, shape).border(1.dp, Line, shape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(symbol, contentDescription = null, tint = Primary, modifier = Modifier.size(20.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(category, color = Primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            Text(title, color = TextPrimary, fontSize = if (compact) 17.sp else 25.sp, lineHeight = if (compact) 22.sp else 30.sp,
                fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis,
                style = LocalTextStyle.current.copy(lineBreak = LineBreak.Heading))
        }
    }
}

@Composable
internal fun NativePagerBar(
    page: NativePageState,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onGoTo: (Int) -> Unit,
    onDirectory: () -> Unit,
    onNarration: () -> Unit,
    onClassmates: () -> Unit,
    onWhiteboard: () -> Unit,
    firstPaintMs: Long?,
    pageFlipMs: Long?,
    peakMemory: Long,
    xp: Int,
    level: Int,
    showMetrics: Boolean,
    compact: Boolean,
    onOpenQuizTools: (() -> Unit)? = null,
) {
    Column(Modifier.fillMaxWidth()) {
        if (page.total == 0) return@Column
        Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
        Column(
            Modifier.fillMaxWidth().background(Background)
                .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom))
                .padding(horizontal = 10.dp, vertical = 3.dp),
        ) {
            if (onOpenQuizTools != null) {
                PageControls(page, onPrev, onNext, onGoTo, Modifier.fillMaxWidth(), onOpenQuizTools)
            } else if (compact) {
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    PageControls(page, onPrev, onNext, onGoTo, Modifier.weight(1f))
                    Box(Modifier.width(1.dp).height(30.dp).background(Line))
                    ClassroomTools(onDirectory, onNarration, onClassmates, onWhiteboard, Modifier.width(216.dp))
                }
            } else {
                PageControls(page, onPrev, onNext, onGoTo, Modifier.fillMaxWidth())
                Box(Modifier.fillMaxWidth().height(1.dp).background(Line.copy(alpha = .65f)))
                ClassroomTools(onDirectory, onNarration, onClassmates, onWhiteboard, Modifier.fillMaxWidth())
            }
            if (showMetrics) {
                Text(
                    "Lv.$level · $xp XP   首屏 ${firstPaintMs?.let { "$it ms" } ?: "—"} · 翻页 ${pageFlipMs?.let { "$it ms" } ?: "—"} · NativeHeap ${peakMemory / (1024 * 1024)} MB",
                    color = Muted, fontSize = 11.sp,
                    modifier = Modifier.padding(start = 6.dp, bottom = 5.dp),
                )
            }
        }
    }
}

@Composable
private fun PageControls(
    page: NativePageState,
    onPrev: () -> Unit,
    onNext: () -> Unit,
    onGoTo: (Int) -> Unit,
    modifier: Modifier,
    onOpenTools: (() -> Unit)? = null,
) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        val textPadding = if (onOpenTools != null) PaddingValues(horizontal = 8.dp) else ButtonDefaults.TextButtonContentPadding
        TextButton(
            onClick = onPrev,
            enabled = page.hasPrev,
            contentPadding = textPadding,
        ) { Text("上一页") }
        Column(
            Modifier.weight(1f).padding(horizontal = 6.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("${page.index + 1} / ${page.total}", color = TextPrimary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
            if (page.total > 1 && onOpenTools == null) {
                var scrub by remember(page.index, page.total) { mutableFloatStateOf(page.index.toFloat()) }
                Slider(
                    value = scrub,
                    onValueChange = { scrub = it },
                    onValueChangeFinished = { onGoTo(scrub.roundToInt()) },
                    valueRange = 0f..(page.total - 1).toFloat(),
                    steps = (page.total - 2).coerceAtLeast(0),
                    modifier = Modifier.fillMaxWidth().height(28.dp),
                    colors = SliderDefaults.colors(thumbColor = Primary, activeTrackColor = Primary, inactiveTrackColor = Line),
                )
            }
        }
        if (onOpenTools == null) {
            CampusScenePrimaryButton(onClick = onNext, enabled = page.hasNext) {
                Text("下一页")
                Spacer(Modifier.width(4.dp))
                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, modifier = Modifier.size(16.dp))
            }
        } else {
            TextButton(onClick = onNext, enabled = page.hasNext, contentPadding = textPadding) {
                Text("下一页")
            }
            IconButton(onClick = onOpenTools) {
                Icon(Icons.Default.MoreVert, contentDescription = "课堂工具", tint = Accent)
            }
        }
    }
}

@Composable
internal fun ClassroomTools(
    onDirectory: () -> Unit,
    onNarration: () -> Unit,
    onClassmates: () -> Unit,
    onWhiteboard: () -> Unit,
    modifier: Modifier,
) {
    Row(modifier) {
        ClassroomTool("目录", Icons.AutoMirrored.Filled.MenuBook, onDirectory, Modifier.weight(1f))
        ClassroomTool("讲解", Icons.AutoMirrored.Filled.VolumeUp, onNarration, Modifier.weight(1f))
        ClassroomTool("同学", Icons.Default.Groups, onClassmates, Modifier.weight(1f))
        ClassroomTool("白板", Icons.Default.BorderColor, onWhiteboard, Modifier.weight(1f))
    }
}

@Composable
private fun ClassroomTool(label: String, icon: ImageVector, onClick: () -> Unit, modifier: Modifier) {
    Column(
        modifier
            .heightIn(min = 48.dp)
            .clip(RoundedCornerShape(9.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .padding(vertical = 5.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Icon(icon, contentDescription = null, tint = Accent, modifier = Modifier.size(19.dp))
        Text(label, color = TextPrimary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
internal fun NativeClassroomActions(
    teachingSlide: Boolean,
    canTeach: Boolean,
    sequence: NativeSequenceUiState,
    actions: List<NativeAction>,
    active: NativeAction?,
    speech: String?,
    teacherSpeaking: Boolean,
    lectureScript: String?,
    onStart: () -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onStop: () -> Unit,
    onAction: (NativeAction) -> Unit,
    onHideSpeech: () -> Unit,
    sidePanel: Boolean,
    modifier: Modifier = Modifier,
) {
    if (!teachingSlide && sequence.total == 0 && actions.isEmpty() && speech == null) return
    val shape = RoundedCornerShape(15.dp)
    Column(
        modifier.fillMaxWidth().then(if (sidePanel) Modifier.fillMaxHeight() else Modifier)
            .background(Surface, shape).border(1.dp, Line, shape).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (teachingSlide || sequence.total > 0) {
            val finished = !sequence.active && sequence.total > 0 && sequence.current >= sequence.total
            val playLabel = when {
                sequence.active && sequence.paused -> if (teachingSlide) "继续讲课" else "继续"
                sequence.active -> if (teachingSlide) "暂停讲课" else "暂停"
                finished -> if (teachingSlide) "重新讲解" else "重播"
                else -> if (teachingSlide) "开始讲课" else "顺序播放"
            }
            val playButton: @Composable (Modifier) -> Unit = { buttonModifier ->
                Button(
                    onClick = when {
                        !sequence.active -> onStart
                        sequence.paused -> onResume
                        else -> onPause
                    },
                    enabled = !teachingSlide || canTeach,
                    modifier = buttonModifier,
                    contentPadding = if (sidePanel) PaddingValues(horizontal = 10.dp, vertical = 8.dp)
                    else ButtonDefaults.ContentPadding,
                    shape = ClassroomActionShape,
                ) {
                    Icon(if (sequence.active && !sequence.paused) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(playLabel, maxLines = 1)
                }
            }
            Row(
                Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(if (sidePanel) 4.dp else 8.dp),
            ) {
                if (teachingSlide && !sidePanel) {
                    Box(
                        Modifier.size(40.dp).background(PrimarySoft, RoundedCornerShape(10.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (teacherSpeaking) {
                            ClassroomTeacherSignal(Modifier.size(22.dp))
                        } else {
                            Icon(Icons.Default.RecordVoiceOver, contentDescription = null, tint = Primary, modifier = Modifier.size(22.dp))
                        }
                    }
                }
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        if (teacherSpeaking && (sidePanel || !teachingSlide)) ClassroomTeacherSignal(Modifier.size(14.dp))
                        Text(if (teachingSlide) "AI 老师" else "本页动作", color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                    }
                    Text(
                        when {
                            finished -> if (teachingSlide) "本页讲完" else "已完成"
                            !teachingSlide -> "${sequence.current}/${sequence.total}"
                            sequence.paused -> "已暂停"
                            sequence.preparing -> "正在准备语音"
                            sequence.active && active?.type == "play_video" -> "演示中"
                            sequence.active -> "正在讲解"
                            !canTeach -> "课件未提供讲稿"
                            else -> "可以开始讲课"
                        },
                        color = Primary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                    )
                }
                playButton(Modifier)
                if (sequence.active) {
                    IconButton(onClick = onStop, modifier = Modifier.width(44.dp)) {
                        Icon(Icons.Default.Stop, "停止", tint = Primary, modifier = Modifier.size(18.dp))
                    }
                }
            }
            if (sequence.total > 1) {
                val finishedSteps = if (sequence.active) sequence.current - 1 else sequence.current
                val reduceMotion = LocalReduceMotion.current
                val stepProgress = animateFloatAsState(
                    (finishedSteps.toFloat() / sequence.total).coerceIn(0f, 1f),
                    animationSpec = if (reduceMotion) snap() else tween(240, easing = CampusMotion.settleEasing),
                    label = "classroom teaching progress",
                )
                LinearProgressIndicator(
                    progress = { stepProgress.value },
                    modifier = Modifier.fillMaxWidth().height(3.dp).clip(RoundedCornerShape(3.dp)),
                    color = Primary,
                    trackColor = Line,
                )
            }
        }
        val transcript = speech?.takeIf(String::isNotBlank) ?: lectureScript
        if (!transcript.isNullOrBlank()) {
            val captionScroll = rememberScrollState()
            var expanded by rememberSaveable { mutableStateOf(true) }
            LaunchedEffect(transcript) { captionScroll.scrollTo(0) }
            Column(
                Modifier.fillMaxWidth().then(if (sidePanel && expanded) Modifier.weight(1f) else Modifier)
                    .background(Background, RoundedCornerShape(9.dp)).padding(horizontal = 10.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.AutoMirrored.Filled.VolumeUp, contentDescription = null, tint = Accent, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(if (speech == null || sequence.fullTranscript) "本页讲稿" else "讲解字幕",
                        color = Accent, fontSize = 12.sp, modifier = Modifier.weight(1f))
                    TextButton(onClick = {
                        expanded = !expanded
                        if (!expanded && speech != null) onHideSpeech()
                    }) { Text(if (expanded) "收起" else "展开") }
                }
                if (expanded) {
                    Text(
                        text = transcript, color = TextPrimary, fontSize = 14.sp, lineHeight = 21.sp,
                        modifier = Modifier.fillMaxWidth()
                            .then(if (sidePanel) Modifier.weight(1f).verticalScroll(captionScroll) else Modifier)
                            .padding(bottom = 10.dp),
                    )
                }
            }
        }
        if (actions.isNotEmpty()) {
            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(7.dp),
            ) {
                actions.forEach { action ->
                    val selected = active?.id == action.id
                    val label = action.title.takeIf { it.isNotBlank() && it != action.type }
                        ?: if (action.supported) action.type else "查看兼容说明"
                    OutlinedButton(
                        onClick = { onAction(action) },
                        shape = RoundedCornerShape(9.dp),
                        border = BorderStroke(1.dp, if (selected) Primary else Line),
                    ) {
                        Text(label, color = if (selected) Primary else TextPrimary,
                            fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.widthIn(max = 145.dp))
                    }
                }
            }
        }
    }
}

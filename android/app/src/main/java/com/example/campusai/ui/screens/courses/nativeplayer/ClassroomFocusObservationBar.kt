package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.focus.ClassroomFocusStatus
import com.example.campusai.data.classroom.focus.ClassroomFocusUiState
import com.example.campusai.data.classroom.focus.ClassroomObservationExportFormat
import com.example.campusai.data.classroom.focus.ClassroomObservationVerdict
import com.example.campusai.data.classroom.focus.ClassroomObservationWindow
import com.example.campusai.ui.components.GlassTextButton as TextButton
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary
import java.util.Locale
import kotlin.math.roundToInt

/**
 * 原生课堂底部的课堂观察条。
 *
 * 非打断式：只占一行事实和一行 Debug 复盘入口，不弹窗、不抢焦点；播放、翻页、
 * 答题保持可用。按钮始终存在，权限对话框未返回或检测器仍在启动时也可点击取消。
 *
 * 状态条只呈现可观察事实，不输出专注/分心结论。Debug 导出入口只在 Debug 构建
 * 且观察已开启并已有窗口时出现；Release 构建不会显示，也不会产生导出文件。
 */
@Composable
internal fun ClassroomFocusObservationBar(
    state: ClassroomFocusUiState,
    busy: Boolean,
    onToggle: () -> Unit,
    onExport: (ClassroomObservationExportFormat) -> Unit,
    exportBusy: Boolean,
    exportNotice: String?,
    modifier: Modifier = Modifier,
) {
    val activeBusy = busy || state.busy
    val statusText = when {
        state.status != null -> buildString {
            append(state.status.label)
            state.reason?.let { append(" · ").append(it.label) }
        }
        activeBusy -> "正在开启…"
        !state.notice.isNullOrBlank() -> state.notice
        else -> "课堂观察未开启"
    }
    val buttonLabel = when {
        state.enabled -> "关闭课堂观察"
        activeBusy -> "取消开启课堂观察"
        else -> "开启课堂观察"
    }
    val dotColor = when (state.status) {
        ClassroomFocusStatus.OBSERVING -> Accent
        ClassroomFocusStatus.RECENT_ACTIVITY -> Primary
        ClassroomFocusStatus.FACE_PRESENT -> Color(0xFF2F7D5C)
        ClassroomFocusStatus.FACE_MISSING -> Color(0xFFB45309)
        ClassroomFocusStatus.UNAVAILABLE -> Color(0xFFB45309)
        null -> Muted
    }
    val textColor = if (state.status == ClassroomFocusStatus.UNAVAILABLE) {
        DangerText
    } else {
        TextPrimary
    }
    val showDebugExport = BuildConfig.DEBUG && state.enabled && state.windowCount > 0

    Column(
        modifier
            .fillMaxWidth()
            .testTag("native.classroom.focus")
            .background(Background)
            .padding(horizontal = 12.dp, vertical = 2.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(Modifier.size(6.dp).background(dotColor, CircleShape))
            Column(
                Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                Text(
                    statusText,
                    color = textColor,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
                val facts = observationFacts(state.latestWindow)
                if (facts != null) {
                    Text(
                        facts,
                        color = Muted,
                        fontSize = 10.sp,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag("native.classroom.focus.facts"),
                    )
                }
            }
            TextButton(
                onClick = onToggle,
                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 0.dp),
                modifier = Modifier
                    .heightIn(min = 40.dp)
                    .testTag("native.classroom.focus.toggle"),
            ) {
                Text(
                    buttonLabel,
                    color = if (state.enabled) DangerText else Accent,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                )
            }
        }
        if (showDebugExport) {
            Row(
                Modifier.fillMaxWidth().testTag("native.classroom.focus.debug"),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text("调试复盘（本机）", color = Muted, fontSize = 10.sp, modifier = Modifier.weight(1f))
                TextButton(
                    onClick = { onExport(ClassroomObservationExportFormat.CSV) },
                    enabled = !exportBusy,
                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp),
                    modifier = Modifier.heightIn(min = 32.dp).testTag("native.classroom.focus.export.csv"),
                ) {
                    Text("导出CSV", fontSize = 10.sp, color = Accent)
                }
                TextButton(
                    onClick = { onExport(ClassroomObservationExportFormat.JSON) },
                    enabled = !exportBusy,
                    contentPadding = PaddingValues(horizontal = 6.dp, vertical = 0.dp),
                    modifier = Modifier.heightIn(min = 32.dp).testTag("native.classroom.focus.export.json"),
                ) {
                    Text("导出JSON", fontSize = 10.sp, color = Accent)
                }
            }
        }
        if (exportNotice != null && showDebugExport) {
            Text(
                exportNotice,
                color = DangerText,
                fontSize = 10.sp,
                modifier = Modifier.padding(bottom = 2.dp),
            )
        }
    }
    Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
}

private fun observationFacts(window: ClassroomObservationWindow?): String? {
    if (window == null) return null
    val activity = "翻页 ${window.manualPageTurns} 交卷 ${window.quizSubmissions} 提问 ${window.questions}"
    if (window.verdict == ClassroomObservationVerdict.UNOBSERVABLE) {
        val reason = window.unavailableReason?.label ?: "有效信号不足"
        // 无法判断与原因是主事实；主动操作作为独立的近期事实继续展示，
        // 既不能覆盖「无法判断」，也不会被无脸/弱光静默丢掉。
        return "10秒窗口无法判断 · $reason · $activity"
    }
    val facePercent = (window.faceVisibleRatio * 100).roundToInt()
    val head = when {
        window.yaw != null && window.pitch != null ->
            "偏航均值 ${degrees(window.yaw.mean)} 俯仰均值 ${degrees(window.pitch.mean)}"
        window.yaw != null -> "偏航均值 ${degrees(window.yaw.mean)} · 俯仰不可用"
        window.pitch != null -> "俯仰均值 ${degrees(window.pitch.mean)} · 偏航不可用"
        else -> "头部角度不可用"
    }
    val stage = stageLabel(window.dominantStage)
    return "10秒窗口：人脸 $facePercent% · $head · $activity · $stage"
}

private fun degrees(value: Double): String = String.format(Locale.US, "%.1f°", value)

private fun stageLabel(stage: String?): String = when (stage) {
    null, "" -> "阶段未知"
    "slide" -> "讲授页"
    "quiz" -> "测验页"
    "interactive" -> "互动页"
    "lecture" -> "讲解中"
    "sandbox_html", "sandbox_url" -> "网页互动页"
    "video" -> "视频页"
    "unavailable" -> "内容不可用"
    else -> stage
}

package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.focus.ClassroomAttentionModelLoad
import com.example.campusai.data.classroom.focus.ClassroomAttentionReminderState
import com.example.campusai.ui.components.GlassTextButton as TextButton
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import java.util.Locale

/**
 * 学生主动开启的课堂提醒。仅在模型产物通过真实数据发布条件时出现正式开关；
 * Debug 构建可加载测试权重，但只显示明确的「调试预览」，不参与正式判断。
 *
 * 提醒只描述可观察窗口，不输出专注度评分、心理判断或学习效果结论；
 * 讲解态和测验页由策略层抑制，学生可暂停、标记「我在记笔记」或反馈误报。
 */
@Composable
internal fun ClassroomAttentionReminderBar(
    model: ClassroomAttentionModelLoad,
    state: ClassroomAttentionReminderState,
    onToggle: (Boolean) -> Unit,
    onPreviewToggle: (Boolean) -> Unit,
    onDismiss: () -> Unit,
    onPause: () -> Unit,
    onResume: () -> Unit,
    onNoteTaking: () -> Unit,
    onFalsePositive: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val artifact = (model as? ClassroomAttentionModelLoad.Ready)?.artifact
    val eligible = artifact?.release?.eligible == true
    val debugPreview = BuildConfig.DEBUG && artifact != null && !eligible
    if (!eligible && !debugPreview) return

    Column(
        modifier
            .fillMaxWidth()
            .testTag("native.classroom.attention")
            .background(Background)
            .padding(horizontal = 12.dp, vertical = 2.dp),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            androidx.compose.foundation.layout.Box(
                Modifier.size(6.dp).background(
                    if (state.processing) Accent else Muted,
                    CircleShape,
                ),
            )
            Column(Modifier.weight(1f)) {
                Text(
                    if (eligible) "课堂提醒（本机）" else "调试：课堂提醒预览（权重未发布）",
                    color = if (eligible) TextPrimary else Muted,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
                if (debugPreview && state.processing && state.lastProbability != null) {
                    Text(
                        "p(离题)=${formatProbability(state.lastProbability)} · 仅开发验证",
                        color = Muted,
                        fontSize = 10.sp,
                    )
                }
            }
            TextButton(
                onClick = {
                    if (eligible) onToggle(!state.enabled) else onPreviewToggle(!state.preview)
                },
                contentPadding = androidx.compose.foundation.layout.PaddingValues(
                    horizontal = 8.dp,
                    vertical = 0.dp,
                ),
                modifier = Modifier
                    .heightIn(min = 40.dp)
                    .testTag("native.classroom.attention.toggle"),
            ) {
                Text(
                    when {
                        state.processing -> "关闭"
                        else -> "开启"
                    },
                    color = Accent,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }

        if (state.reminder != null) {
            androidx.compose.foundation.layout.Box(
                Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp)
                    .background(Surface, androidx.compose.foundation.shape.RoundedCornerShape(10.dp))
                    .padding(horizontal = 10.dp, vertical = 8.dp)
                    .testTag("native.classroom.attention.reminder"),
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        if (state.preview) "调试预览提醒" else "温和提醒",
                        color = Primary,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "最近约 20 秒的可观察信号更像离开当前任务。若你在记笔记、查课内资料或思考，可以忽略。",
                        color = TextPrimary,
                        fontSize = 12.sp,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        TextButton(
                            onClick = onNoteTaking,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 6.dp,
                                vertical = 0.dp,
                            ),
                            modifier = Modifier.heightIn(min = 36.dp).testTag("native.classroom.attention.note"),
                        ) { Text("我在记笔记", color = Accent, fontSize = 11.sp) }
                        TextButton(
                            onClick = onFalsePositive,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 6.dp,
                                vertical = 0.dp,
                            ),
                            modifier = Modifier.heightIn(min = 36.dp).testTag("native.classroom.attention.false"),
                        ) { Text("反馈误报", color = Muted, fontSize = 11.sp) }
                        TextButton(
                            onClick = onPause,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 6.dp,
                                vertical = 0.dp,
                            ),
                            modifier = Modifier.heightIn(min = 36.dp).testTag("native.classroom.attention.pause"),
                        ) { Text("暂停本堂", color = Muted, fontSize = 11.sp) }
                        TextButton(
                            onClick = onDismiss,
                            contentPadding = androidx.compose.foundation.layout.PaddingValues(
                                horizontal = 6.dp,
                                vertical = 0.dp,
                            ),
                            modifier = Modifier.heightIn(min = 36.dp).testTag("native.classroom.attention.dismiss"),
                        ) { Text("知道了", color = TextPrimary, fontSize = 11.sp) }
                    }
                }
            }
        } else if (state.notice != null) {
            Text(
                state.notice,
                color = if (state.paused) DangerText else Muted,
                fontSize = 10.sp,
                modifier = Modifier.padding(top = 2.dp).testTag("native.classroom.attention.notice"),
            )
        }
        if (state.paused) {
            TextButton(
                onClick = onResume,
                contentPadding = androidx.compose.foundation.layout.PaddingValues(
                    horizontal = 6.dp,
                    vertical = 0.dp,
                ),
                modifier = Modifier.heightIn(min = 32.dp).testTag("native.classroom.attention.resume"),
            ) { Text("恢复提醒", color = Accent, fontSize = 11.sp) }
        }
    }
    androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().height(1.dp).background(Line))
}

private fun formatProbability(value: Double?): String =
    value?.let { String.format(Locale.US, "%.2f", it) } ?: "—"

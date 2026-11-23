package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Flag
import androidx.compose.ui.draw.clip
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.NativeAnswer
import com.example.campusai.data.classroom.nativeplayer.NativeQuestion
import com.example.campusai.data.classroom.nativeplayer.NativeQuiz
import com.example.campusai.data.classroom.nativeplayer.NativeQuizOption
import com.example.campusai.data.classroom.nativeplayer.NativeQuizResult
import com.example.campusai.data.classroom.nativeplayer.NativeQuizSubmitState
import com.example.campusai.data.classroom.nativeplayer.NativeQuizUiState
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.SuccessText
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

@Composable
fun NativeQuizPanel(
    quiz: NativeQuiz,
    sceneTitle: String,
    state: NativeQuizUiState?,
    onAnswer: (questionId: String, NativeAnswer) -> Unit,
    onSubmit: () -> Unit,
    onRetry: () -> Unit,
    onSelfCheck: (questionId: String, Boolean) -> Unit,
    onFinishReview: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val quizState = state ?: return
    if (quizState.loading) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator(color = Primary)
        }
        return
    }
    val results = quizState.results
    val score = results.values.sumOf { it.earned }
    val totalPoints = quiz.totalPoints
    val autoResults = results.values.filter { it.correct != null }
    val shortQuestions = quiz.questions.filter { it.isShortAnswer }
    val reviewed = quizState.reviewed
    val report = quizState.showReport
    val submitState = quizState.submitState
    val title = sceneTitle.ifBlank { "课堂挑战" }
    val answeredCount = quiz.questions.count { quizState.answers[it.id]?.hasValue == true }
    val sheet = RoundedCornerShape(16.dp)
    val scrollState = rememberLazyListState()
    LaunchedEffect(report) {
        if (report) scrollState.scrollToItem(0)
    }

    LazyColumn(
        state = scrollState,
        modifier = modifier
            .fillMaxSize()
            .clip(sheet)
            .background(Background)
            .border(1.dp, Line, sheet)
            .padding(horizontal = 14.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column(
                Modifier.fillMaxWidth().background(Surface, RoundedCornerShape(12.dp)).padding(13.dp),
                verticalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Box(
                        Modifier.size(40.dp).background(PrimarySoft, RoundedCornerShape(10.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Flag, contentDescription = null, tint = Primary, modifier = Modifier.size(21.dp))
                    }
                    Column(Modifier.weight(1f)) {
                        Text(
                            if (report) "$title · 结果" else title,
                            color = TextPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold,
                        )
                        Text(
                            if (report) {
                                "得分 ${formatScore(score)} / ${formatScore(totalPoints)} · 答对 ${autoResults.count { it.correct == true }} 题"
                            } else {
                                "满分 ${formatScore(totalPoints)} 分"
                            },
                            color = Muted, fontSize = 13.sp, lineHeight = 17.sp,
                        )
                    }
                }
                if (!report && quiz.questions.isNotEmpty()) {
                    Text(
                        "已作答 $answeredCount / ${quiz.questions.size} 题",
                        color = Primary, fontSize = 12.sp, fontWeight = FontWeight.Medium,
                    )
                    LinearProgressIndicator(
                        progress = { answeredCount.toFloat() / quiz.questions.size },
                        modifier = Modifier.fillMaxWidth().height(4.dp).clip(RoundedCornerShape(4.dp)),
                        color = Primary, trackColor = Line,
                    )
                }
            }
        }
        quiz.issue?.let { issue ->
            item {
                Text(
                    issue,
                    color = DangerText,
                    fontSize = 12.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFFFF3F0), RoundedCornerShape(8.dp))
                        .padding(10.dp),
                )
            }
        }
        if (!report && submitState != NativeQuizSubmitState.Draft) {
            item {
                Text(
                    when (submitState) {
                        NativeQuizSubmitState.Submitting -> "正在提交并等待服务器确认…"
                        NativeQuizSubmitState.Unknown -> "提交结果未确认，退出后重新进入课堂会核对服务器记录。"
                        NativeQuizSubmitState.Failed -> "提交未成功，答案仍保留在当前页面。"
                        else -> ""
                    },
                    color = if (submitState == NativeQuizSubmitState.Failed) DangerText else Accent,
                    fontSize = 12.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFFFF8E8), RoundedCornerShape(8.dp))
                        .padding(10.dp),
                )
            }
        }
        if (quizState.error != null) {
            item {
                Text(
                    quizState.error.orEmpty(),
                    color = DangerText,
                    fontSize = 12.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Color(0xFFFFF2EF), RoundedCornerShape(8.dp))
                        .padding(10.dp),
                )
            }
        }
        if (report) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    ResultBadge(
                        "客观题",
                        "${autoResults.count { it.correct == true }}/${autoResults.size}",
                        SuccessText,
                    )
                    ResultBadge(
                        "主观题",
                        if (shortQuestions.isEmpty()) "无" else "${shortQuestions.count { quizState.selfChecks[it.id] == true }}/${shortQuestions.size} 已核对",
                        Accent,
                    )
                }
            }
        }
        items(quiz.questions, key = { it.id }) { question ->
            QuestionCard(
                question = question,
                answer = quizState.answers[question.id] ?: NativeAnswer(),
                result = results[question.id],
                report = report,
                selfCheck = quizState.selfChecks[question.id],
                onAnswer = { onAnswer(question.id, it) },
                onSelfCheck = { onSelfCheck(question.id, it) },
            )
        }
        item {
            Spacer(Modifier.height(4.dp))
            when {
                !report -> Button(
                    onClick = onSubmit,
                    enabled = !quizState.saving && quiz.issue == null,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (quizState.saving) {
                        CircularProgressIndicator(Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                        Spacer(Modifier.width(8.dp))
                    }
                    Text(
                        when (submitState) {
                            NativeQuizSubmitState.Submitting -> "提交确认中…"
                            NativeQuizSubmitState.Failed,
                            NativeQuizSubmitState.Unknown -> "重新提交"
                            else -> "提交答案"
                        },
                    )
                }
                shortQuestions.isNotEmpty() && !reviewed -> {
                    val allChecked = shortQuestions.all { quizState.selfChecks[it.id] != null }
                    Button(
                        onClick = onFinishReview,
                        enabled = allChecked && !quizState.saving,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (quizState.saving) {
                            CircularProgressIndicator(Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (allChecked) "完成主观题核对" else "请先核对全部主观题")
                    }
                }
                reviewed -> OutlinedButton(onClick = onRetry, modifier = Modifier.fillMaxWidth()) {
                    Text("再做一遍（不重复加分）")
                }
            }
        }
    }
}

@Composable
private fun QuestionCard(
    question: NativeQuestion,
    answer: NativeAnswer,
    result: NativeQuizResult?,
    report: Boolean,
    selfCheck: Boolean?,
    onAnswer: (NativeAnswer) -> Unit,
    onSelfCheck: (Boolean) -> Unit,
) {
    val correct = result?.correct
    val borderColor = when {
        !report -> Line
        correct == true -> SuccessText
        correct == false -> DangerText
        else -> Accent
    }
    Column(
        Modifier
            .fillMaxWidth()
            .border(1.dp, borderColor.copy(alpha = 0.65f), RoundedCornerShape(12.dp))
            .background(Surface, RoundedCornerShape(12.dp))
            .padding(14.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Text(
                "第 ${question.number} 题",
                color = Primary,
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.sp,
            )
            Spacer(Modifier.width(8.dp))
            Text(
                when {
                    question.isShortAnswer -> "主观题"
                    question.isMultiple -> "多选题"
                    else -> "单选题"
                } + " · ${formatScore(question.points)} 分",
                color = Muted,
                fontSize = 11.sp,
                modifier = Modifier.weight(1f),
            )
            if (report) {
                Text(
                    when (correct) {
                        true -> "答对 +${formatScore(result?.earned ?: 0.0)}"
                        false -> "答错"
                        else -> "待核对"
                    },
                    color = when (correct) {
                        true -> SuccessText
                        false -> DangerText
                        else -> Accent
                    },
                    fontSize = 11.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(question.question, color = TextPrimary, fontSize = 15.sp, lineHeight = 22.sp)
        Spacer(Modifier.height(10.dp))

        if (question.isShortAnswer) {
            if (report) {
                Text(
                    "参考答案：${question.answerKey.joinToString("；").ifBlank { "未下发参考答案，请按课堂讲解自行核对" }}",
                    color = Primary,
                    fontSize = 13.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(PrimarySoft, RoundedCornerShape(8.dp))
                        .padding(10.dp),
                )
                Spacer(Modifier.height(8.dp))
                Text("我的作答：${answer.text.ifBlank { "（空）" }}", color = TextPrimary, fontSize = 13.sp)
                if (!result?.selfChecked.orFalse() && selfCheck == null) {
                    Spacer(Modifier.height(10.dp))
                    Text("请对照参考答案自行核对：", color = Muted, fontSize = 12.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { onSelfCheck(true) }) { Text("核对为正确") }
                        OutlinedButton(onClick = { onSelfCheck(false) }) { Text("还需要复习") }
                    }
                } else {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        if (selfCheck == true || result?.selfChecked == true) "已核对为正确" else "已标记为需要复习",
                        color = if (selfCheck == true || result?.selfChecked == true) SuccessText else Accent,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            } else {
                OutlinedTextField(
                    value = answer.text,
                    onValueChange = { onAnswer(NativeAnswer(text = it)) },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    placeholder = { Text("写下你的思路或答案") },
                    label = { Text("你的回答") },
                )
            }
        } else {
            question.options.forEach { option ->
                val selected = answer.selected.contains(option.value) || answer.selected.contains(option.label)
                val answerText = quizOptionText(option)
                val correctOption = report && option.value in question.answerKey
                val highlighted = selected || correctOption
                val optionShape = RoundedCornerShape(9.dp)
                val outline = when {
                    correctOption -> SuccessText
                    report && selected && correct == false -> DangerText
                    selected -> Primary
                    else -> Line
                }
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = 3.dp)
                        .clip(optionShape)
                        .background(if (highlighted) outline.copy(alpha = .10f) else Surface)
                        .border(1.dp, outline.copy(alpha = if (highlighted) .74f else .6f), optionShape)
                        .heightIn(min = 48.dp)
                        .semantics { this.selected = selected }
                        .clickable(enabled = !report, role = if (question.isMultiple) Role.Checkbox else Role.RadioButton) {
                            if (report) return@clickable
                            if (question.isMultiple) {
                                val next = if (selected) answer.selected - option.value else answer.selected + option.value
                                onAnswer(NativeAnswer(selected = next))
                            } else {
                                onAnswer(NativeAnswer(selected = setOf(option.value)))
                            }
                        }
                        .padding(horizontal = 8.dp, vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (question.isMultiple) {
                        Checkbox(checked = selected, onCheckedChange = null, enabled = !report, modifier = Modifier.padding(7.dp))
                    } else {
                        RadioButton(selected = selected, onClick = null, enabled = !report, modifier = Modifier.padding(7.dp))
                    }
                    Text(answerText, color = TextPrimary, fontSize = 14.sp, modifier = Modifier.weight(1f))
                    if (correctOption) {
                        Spacer(Modifier.width(6.dp))
                        Text("正确答案", color = SuccessText, fontSize = 10.sp)
                    }
                }
            }
        }

        if (report) {
            val analysis = result?.comment.orEmpty().ifBlank { question.analysis }
            if (analysis.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "解析：$analysis",
                    color = TextPrimary,
                    fontSize = 12.sp,
                    lineHeight = 18.sp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(PrimarySoft, RoundedCornerShape(8.dp))
                        .padding(10.dp),
                )
            }
        }
    }
}

@Composable
private fun ResultBadge(label: String, value: String, color: Color) {
    Row(
        Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, color = color, fontSize = 11.sp)
        Spacer(Modifier.width(6.dp))
        Text(value, color = color, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
    }
}

private fun formatScore(value: Double): String {
    return if (value % 1.0 == 0.0) value.toInt().toString() else String.format("%.1f", value)
}

/** 对象选项是 value=字母/label=文本，字符串选项相反，统一按「字母. 文本」展示。 */
private fun quizOptionText(option: NativeQuizOption): String {
    if (option.label == option.value) return option.value
    val marker = Regex("^[A-Za-z甲乙丙丁戊己庚辛壬癸]{1,2}$")
    return when {
        marker.matches(option.value) && !marker.matches(option.label) -> "${option.value}. ${option.label}"
        marker.matches(option.label) && !marker.matches(option.value) -> "${option.label}. ${option.value}"
        else -> option.value
    }
}

private fun Boolean?.orFalse(): Boolean = this == true

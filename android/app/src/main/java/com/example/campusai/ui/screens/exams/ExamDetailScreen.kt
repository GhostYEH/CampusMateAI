package com.example.campusai.ui.screens.exams

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.EventBusy
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.ExamStatus
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.FormSwitchRow
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

@Composable
fun ExamDetailScreen(
    examId: Long,
    repository: ExamRepository,
    onBack: () -> Unit,
    onEdit: (Long) -> Unit,
) {
    val exams by repository.exams.collectAsState()
    val exam = exams.find { it.id == examId }
    val scope = rememberCoroutineScope()
    var showDeleteConfirm by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.Exams.DETAIL_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))

        if (exam == null) {
            EmptyState(Icons.Default.EventBusy, CampusStrings.Exams.EMPTY)
        } else {
            val now = System.currentTimeMillis()
            val status = exam.statusAt(now)
            CampusCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        exam.courseName,
                        color = TextPrimary,
                        fontSize = 19.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    StatusTag(
                        text = if (status == ExamStatus.UPCOMING) CampusStrings.Exams.FILTER_UPCOMING else CampusStrings.Exams.FILTER_ENDED,
                        tone = if (status == ExamStatus.UPCOMING) StatusTone.INFO else StatusTone.NEUTRAL,
                    )
                }
                Spacer(Modifier.height(6.dp))
                StatusTag(exam.type, StatusTone.NEUTRAL)
                Spacer(Modifier.height(16.dp))
                DetailRow(Icons.Default.Schedule, CampusStrings.Exams.FIELD_DATE, "${exam.dateLabel()}（${exam.date}）")
                DetailRow(Icons.Default.Schedule, CampusStrings.Exams.FIELD_START, "${exam.startTime} - ${exam.endTime}")
                DetailRow(Icons.Default.LocationOn, CampusStrings.Exams.FIELD_LOCATION, exam.location)
                DetailRow(Icons.Default.Schedule, CampusStrings.Exams.FIELD_SEAT, exam.seatNumber)
            }
            Spacer(Modifier.height(12.dp))
            FormSwitchRow(
                title = CampusStrings.Exams.REMINDER,
                subtitle = if (exam.reminderEnabled) CampusStrings.Exams.REMINDER_ON else CampusStrings.Exams.REMINDER_OFF,
                checked = exam.reminderEnabled,
                onCheckedChange = { enabled ->
                    scope.launch { repository.setReminder(exam.id, enabled) }
                },
            )
            Spacer(Modifier.height(18.dp))
            CampusPrimaryButton(
                text = CampusStrings.Exams.EDIT,
                onClick = { onEdit(exam.id) },
            )
            Spacer(Modifier.height(10.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(46.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(DangerText.copy(alpha = .1f))
                    .campusClickable { showDeleteConfirm = true },
                contentAlignment = Alignment.Center,
            ) {
                Text(CampusStrings.Common.DELETE, color = DangerText, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(120.dp))
        }
    }

    if (showDeleteConfirm && exam != null) {
        ConfirmDialog(
            title = CampusStrings.Exams.DELETE_TITLE,
            message = CampusStrings.Exams.DELETE_MESSAGE,
            confirmText = CampusStrings.Common.DELETE,
            danger = true,
            onConfirm = {
                showDeleteConfirm = false
                scope.launch {
                    repository.delete(exam.id)
                    onBack()
                }
            },
            onDismiss = { showDeleteConfirm = false },
        )
    }
}

@Composable
private fun DetailRow(icon: ImageVector, label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = Primary, modifier = Modifier.size(17.dp))
        Spacer(Modifier.width(10.dp))
        Text(label, color = Muted, fontSize = 12.sp, modifier = Modifier.width(64.dp))
        Text(value, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
    }
}

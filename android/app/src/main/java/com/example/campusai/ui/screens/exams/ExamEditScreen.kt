package com.example.campusai.ui.screens.exams

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Keyboard
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.example.campusai.data.model.Exam
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ExamRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.DateTimeOptions
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.components.FormSwitchRow
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch
import androidx.compose.material3.Text
import androidx.compose.ui.unit.sp

/**
 * 新增 / 编辑考试。[examId] 为 0L 表示新增。
 */
@Composable
fun ExamEditScreen(
    examId: Long,
    repository: ExamRepository,
    appRepository: AppRepository,
    onBack: () -> Unit,
) {
    val exams by repository.exams.collectAsState()
    val courses by appRepository.courses.collectAsState()
    val editing = exams.find { it.id == examId }
    val scope = rememberCoroutineScope()

    val dateOptions = remember { DateTimeOptions.dates(90) }
    val timeOptions = remember { DateTimeOptions.times() }
    val typeOptions = CampusStrings.Exams.TYPES.split(",")

    var courseName by remember(editing?.id) { mutableStateOf(editing?.courseName ?: "") }
    var date by remember(editing?.id) { mutableStateOf(editing?.date ?: "") }
    var startTime by remember(editing?.id) { mutableStateOf(editing?.startTime ?: "") }
    var endTime by remember(editing?.id) { mutableStateOf(editing?.endTime ?: "") }
    var location by remember(editing?.id) { mutableStateOf(editing?.location ?: "") }
    var seat by remember(editing?.id) { mutableStateOf(editing?.seatNumber ?: "") }
    var type by remember(editing?.id) { mutableStateOf(editing?.type ?: typeOptions.first()) }
    var reminder by remember(editing?.id) { mutableStateOf(editing?.reminderEnabled ?: true) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(14.dp))
        CampusCard {
            FormField(label = CampusStrings.Exams.FIELD_COURSE) {
                Column {
                    FormDropdown(
                        options = courses.map { it.name },
                        selected = courseName.ifBlank { null },
                        onSelect = { courseName = it },
                        placeholder = "从课程中选择",
                    )
                    Spacer(Modifier.height(8.dp))
                    CampusTextField(
                        value = courseName,
                        onValueChange = { courseName = it },
                        placeholder = "或手动输入课程名称",
                    )
                }
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_DATE) {
                FormDropdown(
                    options = dateOptions.map { it.first },
                    selected = dateOptions.firstOrNull { it.second == date }?.first,
                    onSelect = { label -> date = dateOptions.first { it.first == label }.second },
                    placeholder = "请选择考试日期",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_START) {
                FormDropdown(
                    options = timeOptions,
                    selected = startTime.ifBlank { null },
                    onSelect = { startTime = it },
                    placeholder = "请选择开始时间",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_END) {
                FormDropdown(
                    options = timeOptions,
                    selected = endTime.ifBlank { null },
                    onSelect = { endTime = it },
                    placeholder = "请选择结束时间",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_LOCATION) {
                CampusTextField(
                    value = location,
                    onValueChange = { location = it },
                    placeholder = "例如：博学楼 1-401",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_SEAT) {
                CampusTextField(
                    value = seat,
                    onValueChange = { seat = it },
                    placeholder = "例如：12",
                    keyboardType = KeyboardType.Number,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Exams.FIELD_TYPE) {
                FormDropdown(
                    options = typeOptions,
                    selected = type,
                    onSelect = { type = it },
                    placeholder = "请选择考试类型",
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        FormSwitchRow(
            title = CampusStrings.Exams.REMINDER,
            subtitle = CampusStrings.Exams.REMINDER_ON,
            checked = reminder,
            onCheckedChange = { reminder = it },
        )
        if (error != null) {
            Spacer(Modifier.height(10.dp))
            Text(error.orEmpty(), color = DangerText, fontSize = 12.sp)
        }
        Spacer(Modifier.height(18.dp))
        CampusPrimaryButton(
            text = CampusStrings.Common.SAVE,
            onClick = {
                val trimmedName = courseName.trim()
                val trimmedLocation = location.trim()
                when {
                    trimmedName.isEmpty() || date.isBlank() || startTime.isBlank() ||
                        endTime.isBlank() || trimmedLocation.isEmpty() ->
                        error = CampusStrings.Exams.ERROR_REQUIRED
                    startTime >= endTime ->
                        error = CampusStrings.Exams.ERROR_TIME_ORDER
                    else -> {
                        error = null
                        scope.launch {
                            repository.upsert(
                                Exam(
                                    id = editing?.id ?: 0L,
                                    courseName = trimmedName,
                                    date = date,
                                    startTime = startTime,
                                    endTime = endTime,
                                    location = trimmedLocation,
                                    seatNumber = seat.trim().ifBlank { "-" },
                                    type = type,
                                    reminderEnabled = reminder,
                                ),
                            )
                            onBack()
                        }
                    }
                }
            },
        )
        Spacer(Modifier.height(120.dp))
    }
}

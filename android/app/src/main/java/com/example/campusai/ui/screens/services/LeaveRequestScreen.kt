package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.LeaveForm
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.AttachmentPickField
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.DateTimeOptions
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun LeaveRequestScreen(
    repository: ServiceRepository,
    onBack: () -> Unit,
    onSubmitted: (Long) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val dateTimeOptions = remember { DateTimeOptions.dateTimes(30) }
    val typeOptions = CampusStrings.Services.LEAVE_TYPES.split(",")

    var type by remember { mutableStateOf("") }
    var startAt by remember { mutableStateOf("") }
    var endAt by remember { mutableStateOf("") }
    var reason by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var attachmentUri by remember { mutableStateOf<String?>(null) }
    var attachmentName by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var showConfirm by remember { mutableStateOf(false) }
    var submitting by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.Services.LEAVE_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))
        CampusCard {
            FormField(label = CampusStrings.Services.LEAVE_TYPE) {
                FilterChipRow(options = typeOptions, selected = type, onSelect = { type = it })
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.LEAVE_START) {
                FormDropdown(
                    options = dateTimeOptions.map { it.first },
                    selected = dateTimeOptions.firstOrNull { it.second == startAt }?.first,
                    onSelect = { label -> startAt = dateTimeOptions.first { it.first == label }.second },
                    placeholder = "请选择开始时间",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.LEAVE_END) {
                FormDropdown(
                    options = dateTimeOptions.map { it.first },
                    selected = dateTimeOptions.firstOrNull { it.second == endAt }?.first,
                    onSelect = { label -> endAt = dateTimeOptions.first { it.first == label }.second },
                    placeholder = "请选择结束时间",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.LEAVE_REASON) {
                CampusTextField(
                    value = reason,
                    onValueChange = { reason = it },
                    placeholder = CampusStrings.Services.LEAVE_REASON_HINT,
                    minLines = 3,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.LEAVE_PHONE) {
                CampusTextField(
                    value = phone,
                    onValueChange = { phone = it.filter(Char::isDigit).take(11) },
                    placeholder = CampusStrings.Services.LEAVE_PHONE_HINT,
                    keyboardType = KeyboardType.Phone,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = "${CampusStrings.Services.LEAVE_ATTACHMENT}（${CampusStrings.Common.OPTIONAL}）") {
                AttachmentPickField(
                    fileName = attachmentName,
                    onPick = { uri, name ->
                        attachmentUri = uri
                        attachmentName = name
                    },
                    hint = CampusStrings.Services.LEAVE_ATTACHMENT_HINT,
                )
            }
        }
        if (error != null) {
            Spacer(Modifier.height(10.dp))
            Text(error.orEmpty(), color = DangerText, fontSize = 12.sp)
        }
        Spacer(Modifier.height(18.dp))
        CampusPrimaryButton(
            text = CampusStrings.Common.SUBMIT,
            enabled = !submitting,
            onClick = {
                val form = LeaveForm(
                    type = type,
                    startAt = startAt,
                    endAt = endAt,
                    reason = reason,
                    phone = phone,
                    attachmentUri = attachmentUri,
                )
                val validation = form.validate()
                if (validation != null) {
                    error = validation
                } else {
                    error = null
                    showConfirm = true
                }
            },
        )
        Spacer(Modifier.height(120.dp))
    }

    if (showConfirm) {
        ConfirmDialog(
            title = CampusStrings.Services.LEAVE_TITLE,
            message = CampusStrings.Services.LEAVE_SUBMIT_CONFIRM,
            confirmText = CampusStrings.Common.SUBMIT,
            onConfirm = {
                showConfirm = false
                submitting = true
                scope.launch {
                    val result = repository.submitLeave(
                        LeaveForm(type, startAt, endAt, reason, phone, attachmentUri),
                    )
                    submitting = false
                    result.onSuccess { onSubmitted(it) }
                        .onFailure { error = it.message }
                }
            },
            onDismiss = { showConfirm = false },
        )
    }
}

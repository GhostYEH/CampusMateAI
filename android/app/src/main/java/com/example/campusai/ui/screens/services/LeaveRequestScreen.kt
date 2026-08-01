package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarToday
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Phone
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
import com.example.campusai.R
import com.example.campusai.data.model.LeaveForm
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.AttachmentPickField
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.DateTimeOptions
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
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
    val typeOptions = listOf("病假", "事假", "公假")
    var type by remember { mutableStateOf("病假") }
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
        modifier = Modifier.fillMaxSize().background(Background).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
    ) {
        ServiceHeroHeader("请假申请", "规范请假流程，保障教学秩序", R.drawable.service_clipboard_hero, onBack)
        ServiceFormCard {
            ServiceSection("请假类型") { ServiceOptionRow(typeOptions, type) { type = it } }
            ServiceSection("开始时间") {
                ServiceSelectField(dateTimeOptions.map { it.first }, dateTimeOptions.firstOrNull { it.second == startAt }?.first.orEmpty(), "请选择开始时间", Icons.Default.CalendarToday) { label ->
                    startAt = dateTimeOptions.first { it.first == label }.second
                }
            }
            ServiceSection("结束时间") {
                ServiceSelectField(dateTimeOptions.map { it.first }, dateTimeOptions.firstOrNull { it.second == endAt }?.first.orEmpty(), "请选择结束时间", Icons.Default.CalendarToday) { label ->
                    endAt = dateTimeOptions.first { it.first == label }.second
                }
            }
            ServiceSection("请假原因") { ServiceInput(reason, { reason = it }, "请说明请假事由（至少 10 个字）", Icons.Default.Edit, lines = 4, maxLength = 200) }
            ServiceSection("联系方式") { ServiceInput(phone, { phone = it.filter(Char::isDigit).take(11) }, "11 位手机号", Icons.Default.Phone, KeyboardType.Phone) }
            ServiceSection("附件（选填）") {
                AttachmentPickField(attachmentName, { uri, name -> attachmentUri = uri; attachmentName = name }, "病历单、证明等（本地选择，不上传）")
            }
        }
        if (error != null) Text(error.orEmpty(), color = DangerText, fontSize = 12.sp, modifier = Modifier.padding(top = 10.dp, start = 8.dp))
        Spacer(Modifier.height(17.dp))
        ServiceNotice("请如实填写申请信息，虚假信息将影响审批结果。")
        Spacer(Modifier.height(14.dp))
        ServiceSubmitButton("提交申请", !submitting) {
            val form = LeaveForm(type, startAt, endAt, reason, phone, attachmentUri)
            error = form.validate()
            if (error == null) showConfirm = true
        }
        Spacer(Modifier.height(BottomDockReservedHeight + 20.dp))
    }
    if (showConfirm) ConfirmDialog(
        title = "请假申请", message = "确认提交请假申请吗？", confirmText = "提交申请",
        onConfirm = {
            showConfirm = false; submitting = true
            scope.launch {
                repository.submitLeave(LeaveForm(type, startAt, endAt, reason, phone, attachmentUri))
                    .onSuccess { onSubmitted(it) }.onFailure { error = it.message }
                submitting = false
            }
        }, onDismiss = { showConfirm = false },
    )
}

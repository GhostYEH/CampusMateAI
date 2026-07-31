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
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

/**
 * 证明申请 / 场地申请 / 意见反馈共用的轻量表单，
 * 提交后同样进入本地申请列表与时间线，不是占位页。
 */
@Composable
fun GenericServiceFormScreen(
    kind: String,
    repository: ServiceRepository,
    onBack: () -> Unit,
    onSubmitted: (Long) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val (title, serviceKind) = when (kind) {
        "certificate" -> CampusStrings.Services.CERTIFICATE to ServiceKind.CERTIFICATE
        "venue" -> CampusStrings.Services.VENUE to ServiceKind.VENUE
        else -> CampusStrings.Services.FEEDBACK to ServiceKind.FEEDBACK
    }

    var summary by remember { mutableStateOf("") }
    var detail by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
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
        CampusPageHeader(title = title, onBack = onBack)
        Spacer(Modifier.height(14.dp))
        CampusCard {
            FormField(label = title) {
                CampusTextField(
                    value = summary,
                    onValueChange = { summary = it },
                    placeholder = when (serviceKind) {
                        ServiceKind.CERTIFICATE -> "例如：在读证明 / 成绩证明"
                        ServiceKind.VENUE -> "例如：博学楼 203 周六下午"
                        else -> "例如：食堂排队时间优化建议"
                    },
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.GENERIC_DESC) {
                CampusTextField(
                    value = detail,
                    onValueChange = { detail = it },
                    placeholder = CampusStrings.Services.GENERIC_DESC_HINT,
                    minLines = 3,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.GENERIC_CONTACT) {
                CampusTextField(
                    value = contact,
                    onValueChange = { contact = it },
                    placeholder = "手机号或邮箱",
                    keyboardType = KeyboardType.Text,
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
                error = when {
                    summary.trim().length < 2 -> "请填写申请内容概要"
                    detail.trim().length < 10 -> "具体说明请至少填写 10 个字"
                    contact.trim().length < 5 -> "请填写联系方式"
                    else -> null
                }
                if (error == null) showConfirm = true
            },
        )
        Spacer(Modifier.height(120.dp))
    }

    if (showConfirm) {
        ConfirmDialog(
            title = title,
            message = "确认提交吗？提交后进入审核流程。",
            confirmText = CampusStrings.Common.SUBMIT,
            onConfirm = {
                showConfirm = false
                submitting = true
                scope.launch {
                    val result = repository.submitGeneric(
                        kind = serviceKind,
                        title = summary,
                        fields = linkedMapOf(
                            "事项" to summary.trim(),
                            "具体说明" to detail.trim(),
                            "联系方式" to contact.trim(),
                        ),
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

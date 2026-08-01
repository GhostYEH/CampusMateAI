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
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.Description
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
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun GenericServiceFormScreen(
    kind: String,
    repository: ServiceRepository,
    onBack: () -> Unit,
    onSubmitted: (Long) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val (title, subtitle, serviceKind, hero) = when (kind) {
        "certificate" -> Quadruple("证明申请", "在线申请各类在校证明，教务审核后发放", ServiceKind.CERTIFICATE, R.drawable.service_clipboard_hero)
        "venue" -> Quadruple("场地申请", "提交教室或场地预约需求，方便快速安排使用", ServiceKind.VENUE, R.drawable.service_clipboard_hero)
        else -> Quadruple("意见反馈", "帮助我们持续优化校园服务体验", ServiceKind.FEEDBACK, R.drawable.service_feedback_hero)
    }
    var summary by remember { mutableStateOf("") }
    var detail by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
    var feedbackType by remember { mutableStateOf("服务建议") }
    var error by remember { mutableStateOf<String?>(null) }
    var showConfirm by remember { mutableStateOf(false) }
    var submitting by remember { mutableStateOf(false) }
    val isFeedback = serviceKind == ServiceKind.FEEDBACK
    val headline = when (serviceKind) {
        ServiceKind.CERTIFICATE -> "在读证明 / 成绩证明"
        ServiceKind.VENUE -> "例如：博学楼 203 周六下午"
        else -> "例如：食堂排队时间优化建议"
    }
    val notice = when (serviceKind) {
        ServiceKind.CERTIFICATE -> "提交后一般在 1–3 个工作日内完成审核，结果将通过站内消息或短信通知。"
        ServiceKind.VENUE -> "提交后将由相关老师审核，审核结果会通过消息通知您。"
        else -> "感谢您的反馈！我们会认真评估并尽快改进。"
    }

    Column(Modifier.fillMaxSize().background(Background).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        ServiceHeroHeader(title, subtitle, hero, onBack)
        ServiceFormCard {
            if (isFeedback) {
                ServiceSection("反馈类型（可选）") { ServiceOptionRow(listOf("服务建议", "功能问题", "体验反馈"), feedbackType) { feedbackType = it } }
                ServiceSection("意见反馈") { ServiceInput(summary, { summary = it }, headline, Icons.Default.Edit, maxLength = 50) }
            } else {
                ServiceSection(if (serviceKind == ServiceKind.CERTIFICATE) "证明申请" else "场地申请") {
                    ServiceInput(summary, { summary = it }, headline, if (serviceKind == ServiceKind.VENUE) Icons.Default.Apartment else Icons.Default.Description)
                }
            }
            ServiceSection("具体说明") { ServiceInput(detail, { detail = it }, "请描述需求或建议（至少 10 个字）", Icons.Default.Edit, lines = 4, maxLength = if (isFeedback) 500 else 200) }
            ServiceSection("联系方式") { ServiceInput(contact, { contact = it }, "手机号或邮箱", Icons.Default.Phone, KeyboardType.Text) }
        }
        if (error != null) Text(error.orEmpty(), color = DangerText, fontSize = 12.sp, modifier = Modifier.padding(top = 10.dp, start = 8.dp))
        Spacer(Modifier.height(17.dp))
        ServiceNotice(notice)
        Spacer(Modifier.height(14.dp))
        ServiceSubmitButton(if (isFeedback) "提交反馈" else "提交申请", !submitting) {
            error = when {
                summary.trim().length < 2 -> "请填写申请内容摘要"
                detail.trim().length < 10 -> "具体说明请至少填写 10 个字"
                contact.trim().length < 5 -> "请填写联系方式"
                else -> null
            }
            if (error == null) showConfirm = true
        }
        Spacer(Modifier.height(BottomDockReservedHeight + 20.dp))
    }
    if (showConfirm) ConfirmDialog(
        title = title, message = "确认提交吗？提交后将进入审核流程。", confirmText = if (isFeedback) "提交反馈" else "提交申请",
        onConfirm = {
            showConfirm = false; submitting = true
            scope.launch {
                repository.submitGeneric(serviceKind, summary, linkedMapOf(
                    "事项" to summary.trim(), "具体说明" to detail.trim(), "联系方式" to contact.trim(),
                    *(if (isFeedback) arrayOf("反馈类型" to feedbackType) else emptyArray()),
                )).onSuccess { onSubmitted(it) }.onFailure { error = it.message }
                submitting = false
            }
        }, onDismiss = { showConfirm = false },
    )
}

private data class Quadruple(val title: String, val subtitle: String, val kind: ServiceKind, val hero: Int)

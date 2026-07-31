package com.example.campusai.data.model

/** 办事大厅事项类型。 */
enum class ServiceKind { LEAVE, REPAIR, CERTIFICATE, VENUE, FEEDBACK }

/** 申请状态，与"我的申请"筛选 Tab 一一对应。 */
enum class RequestStatus { PENDING, APPROVED, REJECTED, COMPLETED }

/** 审核 / 处理进度时间线事件。 */
data class TimelineEvent(
    val time: String,
    val title: String,
    val detail: String,
)

/**
 * 通用办事申请。不同事项的差异字段保存在 [fields]（展示标签 -> 内容），
 * 附件保存本地选择的 Uri 字符串（上传实现由 Repository 隔离，当前为本地记录）。
 */
data class ServiceRequest(
    val id: Long,
    val kind: ServiceKind,
    val title: String,
    val status: RequestStatus,
    val createdAt: String,
    val fields: Map<String, String>,
    val attachmentUris: List<String> = emptyList(),
    val timeline: List<TimelineEvent> = emptyList(),
)

/** 请假申请表单。 */
data class LeaveForm(
    val type: String,
    val startAt: String,
    val endAt: String,
    val reason: String,
    val phone: String,
    val attachmentUri: String?,
) {
    fun validate(): String? = when {
        type.isBlank() -> "请选择请假类型"
        startAt.isBlank() -> "请选择开始时间"
        endAt.isBlank() -> "请选择结束时间"
        startAt >= endAt -> "结束时间需要晚于开始时间"
        reason.trim().length < 10 -> "请假原因请至少填写 10 个字"
        phone.isBlank() -> "请填写联系方式"
        !PHONE_REGEX.matches(phone.trim()) -> "请填写正确的 11 位手机号"
        else -> null
    }

    companion object {
        internal val PHONE_REGEX = Regex("^1\\d{10}$")
    }
}

/** 宿舍报修表单。 */
data class RepairForm(
    val building: String,
    val room: String,
    val type: String,
    val description: String,
    val imageUri: String?,
    val urgency: String,
    val phone: String,
) {
    fun validate(): String? = when {
        building.isBlank() -> "请选择宿舍楼"
        room.isBlank() -> "请填写房间号"
        type.isBlank() -> "请选择报修类型"
        description.trim().length < 10 -> "问题描述请至少填写 10 个字"
        urgency.isBlank() -> "请选择紧急程度"
        !LeaveForm.PHONE_REGEX.matches(phone.trim()) -> "请填写正确的 11 位手机号"
        else -> null
    }
}

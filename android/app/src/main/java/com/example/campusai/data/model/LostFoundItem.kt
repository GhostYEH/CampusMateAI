package com.example.campusai.data.model

enum class LostFoundKind { LOST, FOUND }

/** OPEN = 寻找中 / 待认领；CLOSED = 已找到 / 已归还。 */
enum class LostFoundStatus { OPEN, CLOSED }

/** 失物招领信息。图片保存本地 Uri 字符串，上传由 Repository 隔离（当前无后端接口）。 */
data class LostFoundItem(
    val id: Long,
    val kind: LostFoundKind,
    val title: String,
    val category: String,
    val description: String,
    val time: String,
    val location: String,
    val contact: String,
    val anonymous: Boolean,
    val imageUri: String?,
    val status: LostFoundStatus,
    val publisher: String,
    val mine: Boolean,
    val createdAt: Long,
)

/** 发布表单。 */
data class LostFoundForm(
    val kind: LostFoundKind,
    val title: String,
    val category: String,
    val description: String,
    val time: String,
    val location: String,
    val contact: String,
    val anonymous: Boolean,
    val imageUri: String?,
) {
    fun validate(): String? = when {
        title.trim().length < 2 -> "标题请至少填写 2 个字"
        category.isBlank() -> "请选择物品分类"
        description.trim().length < 10 -> "详细描述请至少填写 10 个字"
        time.isBlank() -> "请选择时间"
        location.isBlank() -> "请填写地点"
        !anonymous && contact.trim().length < 5 -> "请填写联系方式，或选择匿名展示"
        else -> null
    }
}

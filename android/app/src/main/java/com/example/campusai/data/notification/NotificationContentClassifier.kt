package com.example.campusai.data.notification

enum class NotificationContentType { CHAT, NOTICE, ACTIONABLE_NOTICE, AMBIGUOUS }

data class NotificationScore(
    val action: Int = 0,
    val time: Int = 0,
    val campus: Int = 0,
    val material: Int = 0,
    val imperative: Int = 0,
    val hardExcluded: Boolean = false,
    val completed: Boolean = false,
) {
    val actionableTotal: Int get() = action + time + material + imperative
    val noticeTotal: Int get() = campus + time
}

data class Classification(
    val type: NotificationContentType,
    val reason: String,
    val score: NotificationScore,
)

object NotificationContentClassifier {
    private const val ACTIONABLE_THRESHOLD = 5
    private const val NOTICE_THRESHOLD = 3

    private val hardExclusions = listOf(
        "微信支付", "转账成功", "付款成功", "支付成功", "验证码", "校验码",
        "快递已到", "菜鸟驿站", "取件码", "优惠券", "领取红包", "拼团成功",
    )
    private val completions = listOf("已提交", "已完成", "已批阅", "提交成功", "报名成功", "申请成功", "已经报名")
    private val chatExact = setOf("收到", "好的", "好", "嗯", "哦", "明白", "了解", "可以", "没问题", "在吗", "OK", "ok")
    private val chatPatterns = listOf(
        Regex("^(哈|呵|嘿|嘻){2,}.*$"),
        Regex("^\\d+条新消息$"),
        Regex(".*(吃饭|聚餐|天气不错|到宿舍|一起去操场|晚上一起|周末一起).*$"),
    )
    private val actions = listOf("提交", "上交", "交一下", "填写", "签到", "打卡", "参加", "领取", "上传", "申请", "考试", "完成", "选课")
    private val materials = listOf("作业", "实验报告", "报告", "申请表", "报名表", "材料", "论文", "纸质版", "PDF", "证明")
    private val campusAffairs = listOf("学院", "教务", "课程", "班会", "辅导员", "奖学金", "成绩", "图书馆", "停电", "讲座", "考试", "校园", "闭馆", "检修")
    private val imperatives = listOf("请", "务必", "需要", "记得", "尽快", "须", "不要忘记")
    private val timePattern = Regex("(今天|今晚|明天|明晚|后天|本周|下周|周[一二三四五六日天]|\\d{1,2}月\\d{1,2}日|\\d{1,2}[:：点时]\\d{0,2}|截止|之前|前)")

    fun classify(text: String?): Classification {
        val cleaned = NotificationTextSanitizer.clean(text)
            ?: return result(NotificationContentType.CHAT, "empty", NotificationScore())
        if (cleaned.length < 3) return result(NotificationContentType.CHAT, "too_short", NotificationScore())

        val hardExcluded = hardExclusions.any(cleaned::contains)
        val completed = completions.any(cleaned::contains)
        val hasStrongAction = actions.any(cleaned::contains) ||
            (cleaned.contains("报名") && listOf("截止", "请", "填写", "完成", "立即", "尽快").any(cleaned::contains))
        val score = NotificationScore(
            action = if (hasStrongAction) 3 else 0,
            time = if (timePattern.containsMatchIn(cleaned)) 2 else 0,
            campus = if (campusAffairs.any(cleaned::contains)) 2 else 0,
            material = if (materials.any(cleaned::contains)) 2 else 0,
            imperative = if (imperatives.any(cleaned::contains)) 1 else 0,
            hardExcluded = hardExcluded,
            completed = completed,
        )
        if (hardExcluded) return result(NotificationContentType.CHAT, "hard_exclusion", score)
        if (completed) return result(NotificationContentType.CHAT, "completed", score)
        if (cleaned in chatExact || chatPatterns.any { it.matches(cleaned) }) {
            return result(NotificationContentType.CHAT, "chat_pattern", score)
        }
        if (score.actionableTotal >= ACTIONABLE_THRESHOLD && score.action > 0) {
            return result(NotificationContentType.ACTIONABLE_NOTICE, "action_and_context", score)
        }
        if (score.campus > 0 && score.noticeTotal >= NOTICE_THRESHOLD - 1) {
            return result(NotificationContentType.NOTICE, "campus_information", score)
        }
        if (score.action > 0 || cleaned.contains("报名") || (score.imperative > 0 && (score.time > 0 || score.material > 0))) {
            return result(NotificationContentType.AMBIGUOUS, "needs_semantic_review", score)
        }
        return result(NotificationContentType.CHAT, "no_notice_signal", score)
    }

    fun isLikelyNonTask(text: String?): Boolean = classify(text).type == NotificationContentType.CHAT
    fun isHardExcluded(text: String?): Boolean = classify(text).score.hardExcluded
    fun hasActionSignal(text: String?): Boolean = classify(text).let {
        it.score.action > 0 || it.score.imperative > 0
    }

    private fun result(type: NotificationContentType, reason: String, score: NotificationScore) =
        Classification(type, reason, score)
}

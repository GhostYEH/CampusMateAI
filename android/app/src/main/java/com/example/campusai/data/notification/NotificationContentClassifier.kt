package com.example.campusai.data.notification

object NotificationContentClassifier {

    private val nonTaskKeywords = listOf(
        "微信支付", "转账成功", "付款成功", "支付成功",
        "验证码", "验证码是", "校验码",
        "快递已到", "菜鸟驿站", "取件码", "凭取件码",
        "优惠券", "领取红包", "拼团成功",
        "已提交", "已完成", "已批阅", "提交成功", "报名成功", "申请成功",
        "好友申请", "申请加为好友", "我报名了", "已经报名",
        "哈哈哈", "呵呵呵", "笑死",
    )

    private val nonTaskRegexes = listOf(
        Regex("^[嗯好哦OKok行对是的]{1,3}$"),
        Regex("^(晚上|中午|早上|今天|明天).{0,4}(吃|喝|去|玩|走|到|回)"),
        Regex("^(在吗|在不在|到了吗|到哪了|回了吗|起了吗|睡了吗|下班了吗|下课了吗|到宿舍了吗|到宿舍了没)"),
        Regex("^\\d+条新消息$"),
        Regex("^(已读|已收到|收到|明白|了解|知道|好的收到|嗯嗯|好嘞|行吧|可以|没问题)"),
        Regex("(一起|约着?).{0,8}(吃饭|聚餐|喝酒|喝奶茶|出去玩|开黑|去操场)"),
    )

    private val taskKeywords = listOf(
        "截止", "提交", "作业", "实验", "报告", "考试", "报名", "申请",
        "deadline", "DDL", "ddl", "期末", "期中", " quiz", "Quiz",
        "论文", "答辩", "开题", "实习", "实践", "选课", "退课",
        "预约", "借阅", "归还", "签到", "打卡", "上交",
    )

    private val campusAffairsKeywords = listOf(
        "教务", "课程", "班委", "班会", "学院", "辅导员", "奖学金", "助学金",
        "评议", "学分", "成绩", "四六级", "毕业", "开学", "返校", "离校",
        "宿舍", "校园",
    )

    fun classify(text: String?): Classification {
        val cleaned = NotificationTextSanitizer.clean(text) ?: return Classification.IGNORE("空内容")
        if (cleaned.length < 4) return Classification.IGNORE("内容过短")

        hardExclusionReason(cleaned)?.let { return Classification.IGNORE(it) }

        for (kw in taskKeywords) {
            if (cleaned.contains(kw)) return Classification.ACCEPT("事务关键词: $kw")
        }
        for (kw in campusAffairsKeywords) {
            if (cleaned.contains(kw) && hasActionSignal(cleaned)) {
                return Classification.ACCEPT("校园事务关键词: $kw")
            }
        }

        return Classification.IGNORE("未发现校园事务特征")
    }

    fun isLikelyNonTask(text: String?): Boolean = classify(text) is Classification.IGNORE

    fun isHardExcluded(text: String?): Boolean {
        val cleaned = NotificationTextSanitizer.clean(text) ?: return false
        return hardExclusionReason(cleaned) != null
    }

    private fun hardExclusionReason(cleaned: String): String? {
        nonTaskKeywords.firstOrNull(cleaned::contains)?.let { return "非事务关键词: $it" }
        if (nonTaskRegexes.any { it.containsMatchIn(cleaned) }) return "非事务模式匹配"
        return null
    }

    fun hasActionSignal(text: String?): Boolean {
        val cleaned = NotificationTextSanitizer.clean(text) ?: return false
        return listOf("请", "务必", "需要", "尽快", "注意", "查看", "完成", "参加").any(cleaned::contains) ||
            Regex("((今天|明天)(上午|下午|晚上|早上|中午)|本周|下周|周[一二三四五六日天]|\\d{1,2}[:：点时])")
                .containsMatchIn(cleaned)
    }
}

sealed class Classification {
    data class ACCEPT(val reason: String) : Classification()
    data class IGNORE(val reason: String) : Classification()
}

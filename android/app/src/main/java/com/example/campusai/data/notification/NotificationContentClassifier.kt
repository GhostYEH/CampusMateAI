package com.example.campusai.data.notification

object NotificationContentClassifier {

    private val nonTaskKeywords = listOf(
        "微信支付", "转账成功", "付款成功", "支付成功",
        "验证码", "验证码是", "校验码",
        "快递已到", "菜鸟驿站", "取件码", "凭取件码",
        "优惠券", "点击链接", "领取红包", "拼团成功",
        "哈哈哈", "呵呵呵", "笑死",
    )

    private val nonTaskRegexes = listOf(
        Regex("^[嗯好哦OKok行对是的]{1,3}$"),
        Regex("^(晚上|中午|早上|今天|明天).{0,4}(吃|喝|去|玩|走|到|回)"),
        Regex("^(在吗|在不在|到了吗|到哪了|回了吗|起了吗|睡了吗|下班了吗|下课了吗|到宿舍了吗|到宿舍了没)"),
        Regex("^\\d+条新消息$"),
        Regex("^(已读|已收到|收到|明白|了解|知道|好的收到|嗯嗯|好嘞|行吧|可以|没问题)"),
    )

    private val taskKeywords = listOf(
        "截止", "提交", "作业", "实验", "报告", "考试", "报名", "申请",
        "deadline", "DDL", "ddl", "期末", "期中", " quiz", "Quiz",
        "论文", "答辩", "开题", "实习", "实践", "选课", "退课",
        "预约", "借阅", "归还", "签到", "打卡", "上交",
    )

    fun classify(text: String?): Classification {
        val cleaned = NotificationTextSanitizer.clean(text) ?: return Classification.IGNORE("空内容")
        if (cleaned.length < 4) return Classification.IGNORE("内容过短")

        for (kw in nonTaskKeywords) {
            if (cleaned.contains(kw)) return Classification.IGNORE("非事务关键词: $kw")
        }
        for (regex in nonTaskRegexes) {
            if (regex.containsMatchIn(cleaned)) return Classification.IGNORE("非事务模式匹配")
        }

        for (kw in taskKeywords) {
            if (cleaned.contains(kw)) return Classification.ACCEPT("事务关键词: $kw")
        }

        return Classification.ACCEPT("默认候选")
    }

    fun isLikelyNonTask(text: String?): Boolean = classify(text) is Classification.IGNORE
}

sealed class Classification {
    data class ACCEPT(val reason: String) : Classification()
    data class IGNORE(val reason: String) : Classification()
}
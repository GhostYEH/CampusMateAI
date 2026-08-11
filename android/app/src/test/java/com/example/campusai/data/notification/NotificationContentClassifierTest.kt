package com.example.campusai.data.notification

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationContentClassifierTest {

    private fun accept(text: String) = NotificationContentClassifier.classify(text) is Classification.ACCEPT
    private fun ignore(text: String) = NotificationContentClassifier.classify(text) is Classification.IGNORE

    @Test
    fun `chat messages are ignored`() {
        assertFalse(accept("晚上吃什么？"))
        assertFalse(accept("哈哈哈哈"))
        assertFalse(accept("到宿舍了吗？"))
        assertFalse(accept("好的"))
        assertFalse(accept("嗯"))
        assertFalse(accept("在吗"))
        assertFalse(accept("已收到"))
        assertFalse(accept("明白"))
    }

    @Test
    fun `campus assignments are accepted`() {
        assertTrue(accept("数据结构实验三周五23:59前提交到学习通"))
        assertTrue(accept("请提交实验报告"))
        assertTrue(accept("操作系统课程作业截止下周三"))
    }

    @Test
    fun `exam notices are accepted`() {
        assertTrue(accept("高等数学期末考试时间为6月20日上午9点"))
        assertTrue(accept("期中考试安排"))
    }

    @Test
    fun `registration notices are accepted`() {
        assertTrue(accept("英语四级报名截止时间为本周五17:00"))
        assertTrue(accept("竞赛报名通知"))
    }

    @Test
    fun `payment notifications are ignored`() {
        assertFalse(accept("微信支付成功20元"))
        assertFalse(accept("转账成功100元"))
        assertFalse(accept("付款成功"))
    }

    @Test
    fun `verification codes are ignored`() {
        assertFalse(accept("验证码123456"))
        assertFalse(accept("您的验证码是888888"))
    }

    @Test
    fun `express delivery is ignored`() {
        assertFalse(accept("您的快递已到菜鸟驿站"))
        assertFalse(accept("取件码1234"))
    }

    @Test
    fun `ads are ignored`() {
        assertFalse(accept("点击链接领取优惠券"))
        assertFalse(accept("拼团成功"))
    }

    @Test
    fun `wechat aggregated message count is ignored`() {
        assertFalse(accept("3条新消息"))
        assertFalse(accept("5条新消息"))
    }

    @Test
    fun `empty and short content is ignored`() {
        assertFalse(accept(""))
        assertFalse(accept("好"))
        assertFalse(accept("OK"))
    }

    @Test
    fun `campus affairs notices are accepted as candidates`() {
        assertTrue(accept("关于2024级学生选课安排的通知"))
        assertTrue(accept("请各位同学注意查看教务系统"))
        assertTrue(accept("班委通知：明天下午召开奖学金评议会"))
    }

    @Test
    fun `completed campus actions are ignored`() {
        assertFalse(accept("作业已提交"))
        assertFalse(accept("您的申请提交成功"))
        assertFalse(accept("课程作业已批阅，请查看成绩"))
    }

    @Test
    fun `campus task containing a link is still accepted`() {
        assertTrue(accept("请点击链接提交实验报告"))
    }

    @Test
    fun `ordinary unknown chat is ignored instead of becoming a candidate`() {
        assertFalse(accept("今天天气不错，晚点一起去操场吧"))
        assertFalse(accept("照片我已经发到群文件了"))
        assertFalse(accept("今天课程讲得不错，晚上一起吃饭吧"))
        assertFalse(accept("宿舍同学周末一起聚餐"))
    }
}

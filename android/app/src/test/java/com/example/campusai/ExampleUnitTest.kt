package com.example.campusai

import org.junit.Test
import org.junit.Assert.*

class ExampleUnitTest {
    @Test
    fun taskDefaultData_isCorrect() {
        val tasks = listOf(
            Triple("《数据结构》作业三：链表与栈", "今天 23:59", false),
            Triple("《高等数学》习题课报告提交", "明天 20:00", false),
            Triple("\"互联网+\"大赛校内选拔报名", "5月21日 18:00", false),
            Triple("图书馆座位预约", "今天 14:00", true),
        )
        assertEquals(4, tasks.size)
        assertEquals(3, tasks.count { !it.third })
    }

    @Test
    fun mockDemoAccounts_areValid() {
        val demos = mapOf(
            "student_demo" to "student",
        )
        assertTrue(demos.containsKey("student_demo"))
        assertEquals("student", demos["student_demo"])
        assertEquals(1, demos.size)
    }
}

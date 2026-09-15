package com.example.campusai.data.remote

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlin.reflect.full.memberProperties
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 课程上下文传递的合约测试：
 * - ChatRequest 的 course_id 必须以 "course_id" 序列化，且 null 时不写到线上。
 * - 交互课堂 GET 响应只读解析，未启用 / 无 URL 时不给出可打开链接。
 * - 交互课堂 DTO 不承载任何 OpenMAIC 凭据（访问码只在后端）。
 */
class CourseChatContextContractTest {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    @Test
    fun `courseId serializes as course_id`() {
        val request = ChatRequest(message = "请讲解链表", course_id = "course-42")
        val json = moshi.adapter(ChatRequest::class.java).toJson(request)
        assertTrue("course_id 必须按后端字段名序列化: $json", json.contains("\"course_id\":\"course-42\""))
    }

    @Test
    fun `null courseId is omitted from wire payload`() {
        val request = ChatRequest(message = "普通问题")
        val json = moshi.adapter(ChatRequest::class.java).toJson(request)
        assertFalse("null course_id 不应写入线上 payload: $json", json.contains("course_id"))
    }

    @Test
    fun `streamChat style request carries course_id`() {
        // 与 AppRepository.streamChat 构建的请求保持一致，验证 courseId 会沿用到线上字段。
        val asSent = ChatRequest(
            message = "问课程",
            session_id = "android-test",
            stream = true,
            course_id = "course-13",
        )
        val json = moshi.adapter(ChatRequest::class.java).toJson(asSent)
        assertTrue(json.contains("\"course_id\":\"course-13\""))
        assertTrue(json.contains("\"stream\":true"))
    }

    @Test
    fun `interactive classroom enabled exposes only url items`() {
        val json = """
        {"enabled":true,"items":[{"url":"https://class.example.com/1"},{"title":"no-url"},{"url":null}]}
        """.trimIndent()
        val dto = moshi.adapter(InteractiveClassroomDto::class.java).fromJson(json)!!
        assertTrue(dto.enabled)
        assertEquals(listOf("https://class.example.com/1"), dto.existingClassroomUrls())
    }

    @Test
    fun `interactive classroom disabled or empty yields no urls`() {
        val disabled = InteractiveClassroomDto(enabled = false, items = listOf(InteractiveClassroomItemDto(url = "x")))
        val empty = InteractiveClassroomDto(enabled = true, items = emptyList())
        assertEquals(emptyList<String>(), disabled.existingClassroomUrls())
        assertEquals(emptyList<String>(), empty.existingClassroomUrls())
    }

    @Test
    fun `interactive classroom dto never models openmaic credentials`() {
        // OpenMAIC 访问码等凭据只存在于后端；客户端 DTO 不允许出现承载凭据的字段。
        val dtoProps = InteractiveClassroomDto::class.memberProperties.map { it.name }.toSet()
        assertEquals(setOf("enabled", "items"), dtoProps)
        val itemProps = InteractiveClassroomItemDto::class.memberProperties.map { it.name }.toSet()
        assertEquals(setOf("url"), itemProps)
    }

    @Test
    fun `credential-like fields in classroom payload are ignored and never surfaced`() {
        val json = """
        {"enabled":true,
         "embed_origin":"http://127.0.0.1:3000",
         "access_code":"s3cret-value",
         "openmaic_access_code":"s3cret-value",
         "items":[{"url":"http://127.0.0.1:3000/classroom/r1",
                   "access_code":"s3cret-value",
                   "cookie":"openmaic_access=token"}]}
        """.trimIndent()
        val dto = moshi.adapter(InteractiveClassroomDto::class.java).fromJson(json)!!
        assertTrue(dto.enabled)
        assertEquals(listOf("http://127.0.0.1:3000/classroom/r1"), dto.existingClassroomUrls())
        val rendered = dto.toString()
        assertFalse("凭据不得进入客户端模型: $rendered", rendered.contains("s3cret-value"))
        assertFalse("访问码 cookie 不得进入客户端模型: $rendered", rendered.contains("openmaic_access"))
    }
}
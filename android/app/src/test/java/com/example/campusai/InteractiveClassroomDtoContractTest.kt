package com.example.campusai

import com.example.campusai.data.remote.InteractiveClassroomCompositionDto
import com.example.campusai.data.remote.InteractiveClassroomDto
import com.example.campusai.data.remote.InteractiveClassroomGenerateRequest
import com.example.campusai.data.remote.InteractiveClassroomItemDto
import com.example.campusai.data.remote.InteractiveClassroomPlanDto
import com.example.campusai.data.remote.InteractiveClassroomSessionDto
import com.example.campusai.data.remote.InteractiveClassroomStatusDto
import com.example.campusai.data.remote.agent.CounselorSseParser
import com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 互动课堂 DTO 契约测试。
 *
 * 两条硬约束：
 * 1. DTO 里**永远**不出现凭据（ACCESS_CODE / Cookie / Token / Provider Key）；
 * 2. 状态与终态语义必须可区分（configured/available/unavailable/incompatible/degraded、
 *    terminal/retryable/partial），否则 UI 无法给出正确提示。
 */
class InteractiveClassroomDtoContractTest {

    private fun fieldNames(cls: Class<*>): List<String> =
        cls.declaredFields.map { it.name.lowercase() }

    @Test
    fun `no classroom dto carries credentials`() {
        val classes = listOf(
            InteractiveClassroomItemDto::class.java,
            InteractiveClassroomDto::class.java,
            InteractiveClassroomStatusDto::class.java,
            InteractiveClassroomPlanDto::class.java,
            InteractiveClassroomGenerateRequest::class.java,
            InteractiveClassroomSessionDto::class.java,
            InteractiveClassroomCompositionDto::class.java,
            InteractiveClassroomProposalDto::class.java,
        )
        val forbidden = listOf("accesscode", "access_code", "cookie", "token", "apikey", "api_key", "secret", "password")
        classes.forEach { cls ->
            fieldNames(cls).forEach { name ->
                forbidden.forEach { bad ->
                    assertFalse("${cls.simpleName} 不应包含凭据字段: $name", name.contains(bad))
                }
            }
        }
    }

    @Test
    fun `proposal dto carries the server-issued proposal id`() {
        // 没有这个 nonce，客户端无法区分"同一门课的第二个提案"，
        // 于是会复用第一个提案的 job / 幂等键 / 深链。
        val meta = CounselorSseParser.parseFinalMeta(
            """
            {"answer":"","suggested_actions":[{"id":"interactive-classroom","label":"生成",
            "type":"interactiveClassroomProposal","data":{"proposal_id":"icp_abc123",
            "course_id":"c1","course_name":"课程","mode":"quiz","mode_label":"练习测验",
            "intent_note":"意图","available":true,"requires_confirmation":true}}]}
            """.trimIndent(),
        )
        val proposal = meta!!.suggestedActions.single().interactiveClassroomProposal()!!
        assertEquals("icp_abc123", proposal.proposalId)

        // 旧后端不下发该字段时退化为空串，而不是崩溃
        val legacy = CounselorSseParser.parseFinalMeta(
            """
            {"answer":"","suggested_actions":[{"id":"a","label":"生成",
            "type":"interactiveClassroomProposal","data":{"course_id":"c1","course_name":"课程",
            "mode":"quiz","mode_label":"练习测验","intent_note":"意图","available":true,
            "requires_confirmation":true}}]}
            """.trimIndent(),
        )
        assertEquals("", legacy!!.suggestedActions.single().interactiveClassroomProposal()!!.proposalId)
    }

    @Test
    fun `status dto distinguishes all service states`() {
        val status = InteractiveClassroomStatusDto(
            enabled = false,
            configured = true,
            available = false,
            unavailable = true,
            incompatible = false,
            degraded = false,
            embedOrigin = "https://classroom.example.com",
            browserEmbedAvailable = false,
            browserEmbedReason = "需要访问码",
            external3dAvailable = false,
            unavailableCapabilities = listOf("tts"),
        )
        assertTrue(status.configured)
        assertTrue(status.unavailable)
        assertFalse(status.incompatible)
        assertFalse(status.browserEmbedAvailable)
        assertFalse(status.external3dAvailable)
        assertEquals(listOf("tts"), status.unavailableCapabilities)
        assertEquals("https://classroom.example.com", status.embedOrigin)

        val incompatible = status.copy(unavailable = false, incompatible = true)
        assertTrue(incompatible.incompatible)
        assertFalse(incompatible.unavailable)
    }

    @Test
    fun `status defaults are fail-closed`() {
        val empty = InteractiveClassroomStatusDto()
        assertFalse(empty.enabled)
        assertFalse(empty.browserEmbedAvailable)
        assertNull(empty.embedOrigin)
        assertTrue("未配置时也要能生成（由后端决定）", empty.external3dAvailable)
    }

    @Test
    fun `session dto exposes terminal and retryable semantics`() {
        val running = InteractiveClassroomSessionDto(
            sessionId = "om_1",
            status = "running",
            step = "generating_scenes",
            progress = 40,
        )
        assertFalse(running.terminal)
        assertFalse(running.retryable)
        assertFalse(running.partial)
        assertEquals("queued", InteractiveClassroomSessionDto(sessionId = "x").step)

        val failed = running.copy(
            status = "failed",
            step = "failed",
            terminal = true,
            retryable = true,
            errorCode = "OPENMAIC_GENERATION_FAILED",
        )
        assertTrue(failed.terminal)
        assertTrue(failed.retryable)
        assertEquals("OPENMAIC_GENERATION_FAILED", failed.errorCode)
    }

    @Test
    fun `generate request only carries student brief fields`() {
        val request = InteractiveClassroomGenerateRequest(
            mode = "quiz",
            learningObjective = "练熟矩阵乘法",
            desiredDurationMinutes = 20,
            difficultyLevel = "advanced",
            wantsMorePractice = true,
            selectedMaterialIds = listOf("m1"),
        )
        assertEquals("quiz", request.mode)
        assertEquals(20, request.desiredDurationMinutes)
        assertTrue(request.wantsMorePractice)
        assertEquals(listOf("m1"), request.selectedMaterialIds)
        assertNull("未填写的困惑不应被编造", request.currentDifficulty)
    }

    @Test
    fun `composition dto never invents scene types`() {
        val composition = InteractiveClassroomCompositionDto(
            classroomId = "room_1",
            sceneTotal = 2,
            scenes = emptyList(),
            widgetTypes = emptyList(),
            requiresExternal3d = true,
            external3dAvailable = false,
            degraded = true,
        )
        assertEquals(2, composition.sceneTotal)
        assertTrue(composition.scenes.isEmpty())
        assertTrue(composition.degraded)
        assertTrue(composition.requiresExternal3d)
    }

    @Test
    fun `existing classroom urls require enabled flag`() {
        val item = InteractiveClassroomItemDto(url = "https://classroom.example.com/classroom/r1")
        assertEquals(emptyList<String>(), InteractiveClassroomDto(enabled = false, items = listOf(item)).existingClassroomUrls())
        assertEquals(
            listOf("https://classroom.example.com/classroom/r1"),
            InteractiveClassroomDto(enabled = true, items = listOf(item)).existingClassroomUrls(),
        )
    }
}

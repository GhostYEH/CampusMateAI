package com.example.campusai.data.remote.agent

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 验证 Agent Runtime DTO 能正确解析 canonical fixture，
 * 且未知枚举映射 UNKNOWN，不崩溃。
 */
class AgentRuntimeDtoFixtureTest {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    @Test
    fun `runtime fixture job parses with string ids`() {
        val json = """
        {"job_id":"job_01H8XKQD1","user_id":"user_demo_001","job_kind":"final_review",
         "status":"SUCCEEDED","created_at":"2026-09-12T10:00:00+08:00",
         "updated_at":"2026-09-12T10:12:30+08:00","latest_run_id":"run_01H8XKQD2"}
        """.trimIndent()
        val job = moshi.adapter(AgentJobDto::class.java).fromJson(json)!!
        assertEquals("job_01H8XKQD1", job.jobId)
        assertEquals("user_demo_001", job.userId)
        assertEquals(AgentJobKind.final_review, job.kind())
        assertEquals(AgentRunStatus.SUCCEEDED, job.runStatus())
    }

    @Test
    fun `runtime fixture run parses risk level and artifact ids`() {
        val json = """
        {"run_id":"run_01H8XKQD2","job_id":"job_01H8XKQD1","user_id":"user_demo_001",
         "status":"SUCCEEDED","phase":"IDLE","risk_level":"CONFIRM_REQUIRED",
         "started_at":"2026-09-12T10:00:01+08:00","finished_at":"2026-09-12T10:12:30+08:00",
         "created_at":"2026-09-12T10:00:00+08:00","updated_at":"2026-09-12T10:12:30+08:00",
         "error":null,"artifact_ids":["art_01H8XKQD3"]}
        """.trimIndent()
        val run = moshi.adapter(AgentRunDto::class.java).fromJson(json)!!
        assertEquals("run_01H8XKQD2", run.runId)
        assertEquals(AgentRunStatus.SUCCEEDED, run.runStatus())
        assertEquals(AgentRunPhase.IDLE, run.runPhase())
        assertEquals(AgentRiskLevel.CONFIRM_REQUIRED, run.risk())
        assertEquals(listOf("art_01H8XKQD3"), run.artifactIds)
    }

    @Test
    fun `runtime fixture event parses progress and sequence`() {
        val json = """
        {"id":"evt_10002","type":"RUN_STARTED","run_id":"run_01H8XKQD2","sequence":2,
         "status":"RUNNING","phase":"CONTEXT_BUILDING","role":"planner",
         "summary":"开始构建上下文","progress":{"current":0,"total":7,"percent":0},
         "artifact_id":null,"approval_id":null,"created_at":"2026-09-12T10:00:01+08:00"}
        """.trimIndent()
        val event = moshi.adapter(AgentEventDto::class.java).fromJson(json)!!
        assertEquals("evt_10002", event.id)
        assertEquals(2L, event.sequence)
        assertEquals(AgentEventType.RUN_STARTED, event.eventType())
        assertEquals(AgentRunStatus.RUNNING, event.runStatus())
        assertNotNull(event.progress)
        assertEquals(7, event.progress!!.total)
    }

    @Test
    fun `runtime fixture approval parses pending status`() {
        val json = """
        {"approval_id":"apv_nw_001","run_id":"run_nw_001","status":"PENDING",
         "risk_level":"MANUAL_ONLY","action_summary":"在教务系统手动提交作业",
         "expires_at":"2026-09-12T12:35:00+08:00","resolved_at":null,"decision_reason":null}
        """.trimIndent()
        val approval = moshi.adapter(AgentApprovalDto::class.java).fromJson(json)!!
        assertEquals(AgentApprovalStatus.PENDING, approval.approvalStatus())
        assertEquals(AgentRiskLevel.MANUAL_ONLY, approval.risk())
    }

    @Test
    fun `runtime fixture artifact parses type and version`() {
        val json = """
        {"artifact_id":"art_fr_plan_v1","run_id":"run_fr_001","user_id":"user_demo_001",
         "artifact_type":"FINAL_REVIEW_PLAN","version":1,"mime_type":"application/json",
         "size_bytes":4096,"content_hash":"sha256:final_review_v1_hash",
         "download_url":"/api/v1/agent-artifacts/art_fr_plan_v1",
         "created_at":"2026-09-12T10:20:00+08:00"}
        """.trimIndent()
        val artifact = moshi.adapter(AgentArtifactDto::class.java).fromJson(json)!!
        assertEquals(AgentArtifactType.FINAL_REVIEW_PLAN, artifact.type())
        assertEquals(1, artifact.version)
    }

    @Test
    fun `course research fixture parses partial status and policies`() {
        val json = """
        {"run_id":"run_cr_001","job_id":"job_cr_001","question":"解释概念",
         "mode":"EXPLAIN","academic_policy":"LIMITED",
         "source_policy":{"course_material_priority":true,"allow_web":true,"allow_user_upload":true},
         "status":"PARTIAL","phase":"IDLE","risk_level":"AUTO_SAFE",
         "created_at":"","updated_at":"","artifact_ids":["art_cr_report"]}
        """.trimIndent()
        val run = moshi.adapter(CourseResearchRunDto::class.java).fromJson(json)!!
        assertEquals(AgentRunStatus.PARTIAL, run.runStatus())
        assertEquals(AcademicPolicy.LIMITED, run.policy())
        assertEquals(AssistanceMode.EXPLAIN, run.assistance())
        assertNotNull(run.sourcePolicy)
        assertTrue(run.sourcePolicy!!.allowWeb)
    }

    @Test
    fun `notice workflow fixture parses awaiting approval`() {
        val json = """
        {"workflow_id":"wf_001","notice_id":"notice_001","status":"WAITING_CONFIRMATION",
         "summary":"需确认","actions":[],"created_at":"","updated_at":""}
        """.trimIndent()
        val workflow = moshi.adapter(NoticeWorkflowDto::class.java).fromJson(json)!!
        assertEquals(NoticeWorkflowStatus.WAITING_CONFIRMATION, workflow.workflowStatus())
    }

    // ── 未知枚举映射 UNKNOWN，不崩溃 ──

    @Test
    fun `unknown job kind maps to UNKNOWN`() {
        val job = AgentJobDto(jobKind = "future_kind", status = "WEIRD")
        assertEquals(AgentJobKind.UNKNOWN, job.kind())
        assertEquals(AgentRunStatus.UNKNOWN, job.runStatus())
    }

    @Test
    fun `unknown run status phase and risk map to UNKNOWN`() {
        val run = AgentRunDto(status = "NEW_STATUS", phase = "NEW_PHASE", riskLevel = "NEW_RISK")
        assertEquals(AgentRunStatus.UNKNOWN, run.runStatus())
        assertEquals(AgentRunPhase.UNKNOWN, run.runPhase())
        assertEquals(AgentRiskLevel.UNKNOWN, run.risk())
    }

    @Test
    fun `unknown event type maps to UNKNOWN`() {
        val event = AgentEventDto(type = "FUTURE_EVENT")
        assertEquals(AgentEventType.UNKNOWN, event.eventType())
    }

    @Test
    fun `unknown academic policy and assistance mode map to UNKNOWN`() {
        val run = CourseResearchRunDto(academicPolicy = "FUTURE_POLICY", mode = "FUTURE_MODE")
        assertEquals(AcademicPolicy.UNKNOWN, run.policy())
        assertEquals(AssistanceMode.UNKNOWN, run.assistance())
    }

    @Test
    fun `unknown approval status maps to UNKNOWN`() {
        val approval = AgentApprovalDto(status = "FUTURE_STATUS")
        assertEquals(AgentApprovalStatus.UNKNOWN, approval.approvalStatus())
    }

    @Test
    fun `unknown artifact type maps to UNKNOWN`() {
        val artifact = AgentArtifactDto(artifactType = "FUTURE_ARTIFACT")
        assertEquals(AgentArtifactType.UNKNOWN, artifact.type())
    }

    @Test
    fun `unknown citation status maps to UNKNOWN`() {
        val citation = CourseResearchCitationDto(status = "FUTURE_CITATION")
        assertEquals(CitationStatus.UNKNOWN, citation.citationStatus())
    }

    @Test
    fun `unknown notice workflow and action status map to UNKNOWN`() {
        val workflow = NoticeWorkflowDto(status = "FUTURE_WF")
        assertEquals(NoticeWorkflowStatus.UNKNOWN, workflow.workflowStatus())
        val action = NoticeWorkflowActionDto(status = "FUTURE_ACTION")
        assertEquals(NoticeActionStatus.UNKNOWN, action.actionStatus())
    }

    @Test
    fun `null risk level maps to UNKNOWN`() {
        val run = AgentRunDto(riskLevel = null)
        assertEquals(AgentRiskLevel.UNKNOWN, run.risk())
    }
}
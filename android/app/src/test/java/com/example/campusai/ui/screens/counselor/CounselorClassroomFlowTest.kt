package com.example.campusai.ui.screens.counselor

import com.example.campusai.data.remote.agent.AgentApprovalDto
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.CounselorSseParser
import com.example.campusai.data.classroom.ClassroomRestoreRecord
import com.example.campusai.data.classroom.JobPhase
import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CounselorClassroomFlowTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun `done metadata preserves suggested action proposal`() {
        val meta = CounselorSseParser.parseFinalMeta(
            """
            {"answer":"可以生成","conversation_id":"conv-1","suggested_actions":[{"id":"interactive-classroom","label":"生成互动课堂","type":"interactiveClassroomProposal","data":{"course_id":"course-42","course_name":"数据结构","mode":"quiz","mode_label":"练习测验","intent_note":"内容形态只是生成意图","available":true,"requires_confirmation":true}}]}
            """.trimIndent(),
        )

        assertEquals("conv-1", meta?.conversationId)
        val proposal = meta?.suggestedActions?.single()?.interactiveClassroomProposal()
        assertEquals("course-42", proposal?.courseId)
        assertEquals("quiz", proposal?.mode)
        assertTrue(proposal?.available == true)
        assertTrue(proposal?.requiresConfirmation == true)
    }

    @Test
    fun `cpm confirmation creates one queued job and approval only resumes same job`() = runTest(dispatcher) {
        val gateway = FakeCpmClassroomGateway()
        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, _, emit -> emit("回答") },
            classroomGateway = gateway,
            classroomDelay = {},
            autoObserveClassroomJobs = false,
        )
        viewModel.acceptClassroomProposal(
            CounselorSseParser.parseFinalMeta(
                """{"answer":"","suggested_actions":[{"id":"a","label":"生成","type":"interactiveClassroomProposal","data":{"course_id":"c1","course_name":"课程","mode":"quiz","mode_label":"练习测验","available":true,"requires_confirmation":true}}]}""",
            )!!.suggestedActions.single().interactiveClassroomProposal()!!,
        )

        viewModel.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(1, gateway.createCalls)
        assertEquals("c1", gateway.lastCourseId)
        assertEquals(JobPhase.QUEUED, viewModel.uiState.value.classroomJob.phase)

        gateway.jobs = listOf(
            AgentJobDto(
                jobId = "job-1",
                jobKind = "interactive_classroom",
                status = "AWAITING_APPROVAL",
                latestRunId = "run-1",
                pendingApprovalId = "approval-1",
            ),
        )
        viewModel.refreshClassroomJob()
        advanceUntilIdle()
        assertEquals(JobPhase.AWAITING_APPROVAL, viewModel.uiState.value.classroomJob.phase)
        assertTrue(viewModel.uiState.value.classroomJob.canApprove)

        viewModel.approveClassroomProposal()
        advanceUntilIdle()
        assertEquals(1, gateway.approveCalls)
        assertEquals(1, gateway.createCalls)
        assertEquals("job-1", viewModel.uiState.value.classroomJob.jobId)
        assertFalse(viewModel.uiState.value.classroomJob.canApprove)
    }

    @Test
    fun `restored cpm job does not create a second job`() = runTest(dispatcher) {
        // 恢复记录是**一个整体**：进程重建后重新拿到同一个提案（同账号 + 同课程 + 同模式，
        // 任务仍在途）时，必须续跑同一个 job，而不是再建一个。
        val gateway = FakeCpmClassroomGateway()
        val handle = SavedStateHandle()
        ClassroomRestoreRecord(
            fingerprint = "old-fingerprint",
            identity = "user-1",
            courseId = "c1",
            mode = "quiz",
            jobId = "job-restored",
            idempotencyKey = "key-restored",
            phase = JobPhase.QUEUED.name,
        ).writeTo(handle)

        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, _, emit -> emit("回答") },
            classroomGateway = gateway,
            savedStateHandle = handle,
            autoObserveClassroomJobs = false,
            classroomDelay = {},
            identityProvider = { "user-1" },
        )
        advanceUntilIdle()

        viewModel.acceptClassroomProposal(
            CounselorSseParser.parseFinalMeta(
                """{"answer":"","suggested_actions":[{"id":"a","label":"生成","type":"interactiveClassroomProposal","data":{"proposal_id":"icp-new","course_id":"c1","course_name":"课程","mode":"quiz","mode_label":"练习测验","available":true,"requires_confirmation":true}}]}""",
            )!!.suggestedActions.single().interactiveClassroomProposal()!!,
        )
        advanceUntilIdle()

        assertEquals("绝不重复创建", 0, gateway.createCalls)
        assertEquals("job-restored", viewModel.uiState.value.classroomJob.jobId)
    }

    @Test
    fun `restored record from another account is discarded`() = runTest(dispatcher) {
        val gateway = FakeCpmClassroomGateway()
        val handle = SavedStateHandle()
        ClassroomRestoreRecord(
            fingerprint = "old-fingerprint",
            identity = "user-1",
            courseId = "c1",
            mode = "quiz",
            jobId = "job-restored",
            idempotencyKey = "key-restored",
            phase = JobPhase.QUEUED.name,
        ).writeTo(handle)

        val viewModel = CounselorViewModel(
            streamer = CpmChatStreamer { _, _, _, emit -> emit("回答") },
            classroomGateway = gateway,
            savedStateHandle = handle,
            autoObserveClassroomJobs = false,
            classroomDelay = {},
            identityProvider = { "user-2" },
        )
        advanceUntilIdle()

        viewModel.acceptClassroomProposal(
            CounselorSseParser.parseFinalMeta(
                """{"answer":"","suggested_actions":[{"id":"a","label":"生成","type":"interactiveClassroomProposal","data":{"proposal_id":"icp-new","course_id":"c1","course_name":"课程","mode":"quiz","mode_label":"练习测验","available":true,"requires_confirmation":true}}]}""",
            )!!.suggestedActions.single().interactiveClassroomProposal()!!,
        )
        advanceUntilIdle()

        assertNull("别的账号的 job 绝不能被恢复", viewModel.uiState.value.classroomJob.jobId)
    }

    private class FakeCpmClassroomGateway : CpmClassroomGateway {
        var createCalls = 0
        var approveCalls = 0
        var lastCourseId: String? = null
        var jobs = listOf(AgentJobDto(jobId = "job-1", jobKind = "interactive_classroom", status = "QUEUED", latestRunId = "run-1"))

        override suspend fun create(
            courseId: String,
            mode: String,
            idempotencyKey: String,
        ): Result<AgentJobDto> {
            createCalls += 1
            lastCourseId = courseId
            return Result.success(jobs.first())
        }

        override suspend fun get(jobId: String): Result<AgentJobDto> = Result.success(jobs.last())

        override suspend fun decide(approvalId: String, approved: Boolean): Result<AgentApprovalDto> {
            approveCalls += 1
            jobs = listOf(jobs.last().copy(status = "QUEUED", pendingApprovalId = null))
            return Result.success(AgentApprovalDto(approvalId = approvalId, runId = "run-1", status = "APPROVED"))
        }
    }
}

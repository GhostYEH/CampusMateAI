package com.example.campusai.ui.screens.counselor

import androidx.lifecycle.SavedStateHandle
import com.example.campusai.data.classroom.ClassroomProposalScope
import com.example.campusai.data.classroom.ClassroomRestoreRecord
import com.example.campusai.data.classroom.JobPhase
import com.example.campusai.data.remote.agent.AgentApprovalDto
import com.example.campusai.data.remote.agent.AgentJobDto
import com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto
import kotlinx.coroutines.CompletableDeferred
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
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * CPM 提案作用域：跨提案 / 跨课程 / 跨账号 / 进程重建的状态隔离。
 *
 * 修复前的真实故障：
 *  - `acceptClassroomProposal()` 只替换 proposal，不清 `classroomJob`、不取消轮询、
 *    不动 SavedStateHandle 里的 jobId / idempotencyKey；
 *  - 于是第一次成功后收到第二个提案会继续显示旧深链；
 *  - 第一次失败后收到第二个提案会复用旧幂等键，拿到旧响应或 409；
 *  - 进程重建后恢复出的是上一个提案的 job。
 */
@OptIn(ExperimentalCoroutinesApi::class)
class CounselorClassroomScopeTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun proposal(
        courseId: String = "c1",
        mode: String = "review",
        proposalId: String = "icp-1",
        courseName: String = "高等数学",
    ) = InteractiveClassroomProposalDto(
        proposalId = proposalId,
        courseId = courseId,
        courseName = courseName,
        mode = mode,
        modeLabel = "考前复习",
        intentNote = "内容形态只是生成意图",
        available = true,
        requiresConfirmation = true,
    )

    private fun viewModel(
        gateway: RecordingGateway,
        handle: SavedStateHandle = SavedStateHandle(),
        identity: String = "user-1",
    ) = CounselorViewModel(
        streamer = CpmChatStreamer { _, _, _, emit -> emit("回答") },
        classroomGateway = gateway,
        savedStateHandle = handle,
        classroomDelay = {},
        autoObserveClassroomJobs = false,
        identityProvider = { identity },
    )

    // ===== 1. 第一次成功后接收第二个提案 =====

    @Test
    fun `second proposal after a successful job starts clean and creates a new job`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(1, gateway.createCalls)

        // 第一个任务成功并带回深链
        gateway.respondGet(
            AgentJobDto(
                jobId = "job-1",
                jobKind = "interactive_classroom",
                status = "SUCCEEDED",
                latestRunId = "run-1",
                inputRef = mapOf("deep_link" to "/courses/c1?tab=mentoring&session=om-1"),
            ),
        )
        vm.refreshClassroomJob()
        advanceUntilIdle()
        assertEquals(JobPhase.SUCCEEDED, vm.uiState.value.classroomJob.phase)
        assertEquals("/courses/c1?tab=mentoring&session=om-1", vm.uiState.value.classroomJob.deepLink)

        // 第二个提案（同课程、不同 nonce）
        vm.acceptClassroomProposal(proposal(proposalId = "icp-2"))
        assertNull("新提案不得继承旧 jobId", vm.uiState.value.classroomJob.jobId)
        assertNull("新提案不得显示旧深链", vm.uiState.value.classroomJob.deepLink)
        assertEquals(JobPhase.IDLE, vm.uiState.value.classroomJob.phase)
        assertTrue("新提案必须可以再次确认", vm.uiState.value.classroomJob.canConfirm)

        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(2, gateway.createCalls)
        assertNotEquals(
            "新提案必须换新的幂等键",
            gateway.createKeys[0],
            gateway.createKeys[1],
        )
    }

    // ===== 2. 第一次失败后接收第二个提案 =====

    @Test
    fun `second proposal after a failed job does not reuse the old idempotency key`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        gateway.createFailures.add(IllegalStateException("网络错误"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(JobPhase.FAILED, vm.uiState.value.classroomJob.phase)
        assertEquals(1, gateway.createCalls)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-2"))
        assertEquals(JobPhase.IDLE, vm.uiState.value.classroomJob.phase)
        assertEquals("", vm.uiState.value.classroomJob.error)

        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(2, gateway.createCalls)
        assertNotEquals(
            "失败任务不能污染下一次提案的幂等键",
            gateway.createKeys[0],
            gateway.createKeys[1],
        )
    }

    // ===== 3. 同课程不同模式 / 不同课程 =====

    @Test
    fun `same course different mode is a different proposal`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(mode = "review", proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        vm.acceptClassroomProposal(proposal(mode = "quiz", proposalId = "icp-1"))
        assertNull(vm.uiState.value.classroomJob.jobId)
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        assertEquals(2, gateway.createCalls)
        assertEquals(listOf("review", "quiz"), gateway.createModes)
    }

    @Test
    fun `different course is a different proposal`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(courseId = "c1", proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        vm.acceptClassroomProposal(proposal(courseId = "c2", proposalId = "icp-1"))
        assertNull(vm.uiState.value.classroomJob.jobId)
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        assertEquals(listOf("c1", "c2"), gateway.createCourses)
    }

    // ===== 4. 同一个提案重挂载 =====

    @Test
    fun `same proposal remount keeps the same job and does not create again`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals("job-1", vm.uiState.value.classroomJob.jobId)

        // 同一个提案（同 nonce）再次到达
        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        assertEquals("job-1", vm.uiState.value.classroomJob.jobId)
        assertEquals(1, gateway.createCalls)
    }

    // ===== 5. 进程重建 =====

    @Test
    fun `process rebuild resumes the same in-flight job instead of creating a new one`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val gateway = RecordingGateway()
        val first = viewModel(gateway, handle)
        first.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        first.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(1, gateway.createCalls)
        assertEquals("job-1", first.uiState.value.classroomJob.jobId)

        // 进程重建：同一个 SavedStateHandle，全新的 ViewModel；
        // 同一条 SSE 重放会带来**新的** nonce（旧 nonce 随进程一起丢了）
        val rebuilt = viewModel(gateway, handle)
        rebuilt.acceptClassroomProposal(proposal(proposalId = "icp-2"))
        advanceUntilIdle()

        assertEquals("必须续跑同一个 job", "job-1", rebuilt.uiState.value.classroomJob.jobId)
        assertEquals("绝不重复生成", 1, gateway.createCalls)
        assertEquals(JobPhase.QUEUED, rebuilt.uiState.value.classroomJob.phase)
    }

    @Test
    fun `process rebuild after a terminal job does not reuse it`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val gateway = RecordingGateway()
        val first = viewModel(gateway, handle)
        first.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        first.confirmClassroomProposal()
        advanceUntilIdle()
        gateway.respondGet(
            AgentJobDto(
                jobId = "job-1",
                jobKind = "interactive_classroom",
                status = "FAILED",
                latestRunId = "run-1",
            ),
        )
        first.refreshClassroomJob()
        advanceUntilIdle()
        assertEquals(JobPhase.FAILED, first.uiState.value.classroomJob.phase)

        val rebuilt = viewModel(gateway, handle)
        rebuilt.acceptClassroomProposal(proposal(proposalId = "icp-2"))
        assertNull("终态任务不得被新提案复用", rebuilt.uiState.value.classroomJob.jobId)
        rebuilt.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(2, gateway.createCalls)
        assertNotEquals(gateway.createKeys[0], gateway.createKeys[1])
    }

    // ===== 6. 创建响应丢失 =====

    @Test
    fun `retry after a network failure reuses the same idempotency key`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        gateway.createFailures.add(IllegalStateException("timeout"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(JobPhase.FAILED, vm.uiState.value.classroomJob.phase)

        // 同一个提案重试（按钮从"确认生成"变成"重新发起"）
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(2, gateway.createCalls)
        assertEquals(
            "同一提案内重试必须复用同一个幂等键，否则会重复生成",
            gateway.createKeys[0],
            gateway.createKeys[1],
        )
    }

    // ===== 7. 旧轮询迟到 =====

    @Test
    fun `late response from the previous proposal never overwrites the new one`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)

        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        // 发起一次查询但不让它返回（模拟"迟到"）
        gateway.deferNextGet = true
        vm.refreshClassroomJob()
        advanceUntilIdle() // 让协程真正发出请求并挂起在响应上

        // 切到新提案
        vm.acceptClassroomProposal(proposal(courseId = "c2", proposalId = "icp-2"))
        assertNull(vm.uiState.value.classroomJob.jobId)

        // 旧查询此刻才返回，并带着旧 job 的深链
        gateway.completeDeferredGet(
            AgentJobDto(
                jobId = "job-1",
                jobKind = "interactive_classroom",
                status = "SUCCEEDED",
                latestRunId = "run-1",
                inputRef = mapOf("deep_link" to "/courses/c1?tab=mentoring&session=om-1"),
            ),
        )
        advanceUntilIdle()

        assertNull("旧响应不得写进新提案", vm.uiState.value.classroomJob.jobId)
        assertNull("旧深链不得出现在新提案上", vm.uiState.value.classroomJob.deepLink)
        assertEquals(JobPhase.IDLE, vm.uiState.value.classroomJob.phase)
    }

    // ===== 8. 快速重复点击 =====

    @Test
    fun `rapid double confirm creates exactly one job`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)
        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))

        vm.confirmClassroomProposal()
        vm.confirmClassroomProposal()
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        assertEquals(1, gateway.createCalls)
    }

    // ===== 9. 身份变化 / 登出 =====

    @Test
    fun `identity change clears the restore record and the job state`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val gateway = RecordingGateway()
        val vm = viewModel(gateway, handle, identity = "user-1")
        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertNotNull(ClassroomRestoreRecord.read(handle))

        vm.onClassroomIdentityChanged("user-2")

        assertNull("换账号后恢复记录必须整体清除", ClassroomRestoreRecord.read(handle))
        assertNull(vm.uiState.value.classroomProposal)
        assertNull(vm.uiState.value.classroomJob.jobId)
    }

    @Test
    fun `logout clears the restore record`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val gateway = RecordingGateway()
        val vm = viewModel(gateway, handle)
        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()
        assertNotNull(ClassroomRestoreRecord.read(handle))

        vm.onClassroomSessionEnded()

        assertNull(ClassroomRestoreRecord.read(handle))
        assertNull(vm.uiState.value.classroomJob.jobId)
    }

    @Test
    fun `another account cannot resume the previous account's job`() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val gateway = RecordingGateway()
        val first = viewModel(gateway, handle, identity = "user-1")
        first.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        first.confirmClassroomProposal()
        advanceUntilIdle()
        assertEquals(1, gateway.createCalls)

        // 账号 B 登录（同一 SavedStateHandle，全新 ViewModel）
        val second = viewModel(gateway, handle, identity = "user-2")
        second.acceptClassroomProposal(proposal(proposalId = "icp-2"))
        assertNull("B 不得恢复 A 的 job", second.uiState.value.classroomJob.jobId)
    }

    // ===== 10. 审批 =====

    @Test
    fun `approval continues the same job and never creates another`() = runTest(dispatcher) {
        val gateway = RecordingGateway()
        val vm = viewModel(gateway)
        vm.acceptClassroomProposal(proposal(proposalId = "icp-1"))
        vm.confirmClassroomProposal()
        advanceUntilIdle()

        gateway.respondGet(
            AgentJobDto(
                jobId = "job-1",
                jobKind = "interactive_classroom",
                status = "AWAITING_APPROVAL",
                latestRunId = "run-1",
                pendingApprovalId = "approval-1",
            ),
        )
        vm.refreshClassroomJob()
        advanceUntilIdle()
        assertTrue(vm.uiState.value.classroomJob.canApprove)

        vm.approveClassroomProposal()
        advanceUntilIdle()

        assertEquals(1, gateway.approveCalls)
        assertEquals(1, gateway.createCalls)
        assertEquals("job-1", vm.uiState.value.classroomJob.jobId)
        assertNull(vm.uiState.value.classroomJob.approvalId)
    }

    // ===== 11. 指纹本身 =====

    @Test
    fun `fingerprint binds identity proposal nonce course and mode`() {
        val base = proposal()
        val fp = { identity: String, p: InteractiveClassroomProposalDto ->
            ClassroomProposalScope.fingerprint(identity, p)
        }
        assertEquals(fp("u1", base), fp("u1", base.copy()))
        assertNotEquals(fp("u1", base), fp("u2", base))
        assertNotEquals(fp("u1", base), fp("u1", base.copy(courseId = "c9")))
        assertNotEquals(fp("u1", base), fp("u1", base.copy(mode = "quiz")))
        assertNotEquals(fp("u1", base), fp("u1", base.copy(proposalId = "icp-9")))
    }

    @Test
    fun `restore record read is all-or-nothing`() {
        val handle = SavedStateHandle()
        ClassroomRestoreRecord(
            fingerprint = "f",
            identity = "u1",
            courseId = "c1",
            mode = "review",
            jobId = "job-1",
            idempotencyKey = "key-1",
        ).writeTo(handle)
        val record = ClassroomRestoreRecord.read(handle)
        assertNotNull(record)
        assertEquals("job-1", record!!.jobId)

        // 只删掉一个必需字段 → 整条记录视为不存在（绝不部分恢复）
        handle.remove<String>(ClassroomRestoreRecord.KEY_IDEMPOTENCY)
        assertNull(ClassroomRestoreRecord.read(handle))

        ClassroomRestoreRecord.clearFrom(handle)
        assertNull(ClassroomRestoreRecord.read(handle))
    }

    // ===== 测试替身 =====

    private class RecordingGateway : CpmClassroomGateway {
        var createCalls = 0
        var approveCalls = 0
        val createKeys = mutableListOf<String>()
        val createCourses = mutableListOf<String>()
        val createModes = mutableListOf<String>()
        val createFailures = mutableListOf<Throwable>()
        private var lastCreated: AgentJobDto? = null
        private var nextGetOverride: AgentJobDto? = null
        var deferNextGet = false
        private var deferredGet: CompletableDeferred<Result<AgentJobDto>>? = null
        private var jobSeq = 0

        /** 指定下一次 `get` 的返回（覆盖"刚创建的那个 QUEUED 任务"）。 */
        fun respondGet(job: AgentJobDto) {
            nextGetOverride = job
        }

        fun completeDeferredGet(job: AgentJobDto) {
            deferredGet?.complete(Result.success(job))
            deferredGet = null
        }

        override suspend fun create(
            courseId: String,
            mode: String,
            idempotencyKey: String,
        ): Result<AgentJobDto> {
            createCalls += 1
            createKeys += idempotencyKey
            createCourses += courseId
            createModes += mode
            createFailures.removeFirstOrNull()?.let { return Result.failure(it) }
            jobSeq += 1
            val job = AgentJobDto(
                jobId = "job-$jobSeq",
                jobKind = "interactive_classroom",
                status = "QUEUED",
                latestRunId = "run-$jobSeq",
            )
            lastCreated = job
            return Result.success(job)
        }

        override suspend fun get(jobId: String): Result<AgentJobDto> {
            if (deferNextGet) {
                deferNextGet = false
                val deferred = CompletableDeferred<Result<AgentJobDto>>()
                deferredGet = deferred
                return deferred.await()
            }
            nextGetOverride?.let {
                nextGetOverride = null
                return Result.success(it)
            }
            return Result.success(
                lastCreated?.copy(jobId = jobId)
                    ?: AgentJobDto(jobId = jobId, jobKind = "interactive_classroom", status = "QUEUED"),
            )
        }

        override suspend fun decide(approvalId: String, approved: Boolean): Result<AgentApprovalDto> {
            approveCalls += 1
            return Result.success(
                AgentApprovalDto(approvalId = approvalId, runId = "run-1", status = "APPROVED"),
            )
        }
    }
}

package com.example.campusai

import com.example.campusai.data.classroom.ClassroomCompositionText
import com.example.campusai.data.classroom.ClassroomIntent
import com.example.campusai.data.classroom.ClassroomIntentCatalog
import com.example.campusai.data.classroom.ClassroomJobMachine
import com.example.campusai.data.classroom.ClassroomJobState
import com.example.campusai.data.classroom.ClassroomPhase
import com.example.campusai.data.classroom.ClassroomProgressReducer
import com.example.campusai.data.classroom.ClassroomProgressState
import com.example.campusai.data.classroom.JobPhase
import com.example.campusai.data.classroom.JobSnapshot
import com.example.campusai.data.remote.InteractiveClassroomCompositionDto
import com.example.campusai.data.remote.InteractiveClassroomSceneCountDto
import com.example.campusai.data.remote.InteractiveClassroomWidgetCountDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 互动课堂学生端纯逻辑：9 意图、进度状态、真实组成、CPM 异步状态机。
 *
 * 这些都是无 Android 依赖的纯 Kotlin，因此可以在 JVM 单测里直接驱动，
 * 不需要 Robolectric。
 */
class ClassroomStudentFlowTest {

    // ===== A. 9 个生成意图 =====

    @Test
    fun `nine canonical intents`() {
        assertEquals(9, ClassroomIntentCatalog.all.size)
        assertEquals(
            listOf(
                "adaptive", "explain", "quiz", "simulation", "visualization",
                "mindmap", "coding", "pbl", "review",
            ),
            ClassroomIntentCatalog.all.map { it.wire },
        )
        ClassroomIntentCatalog.all.forEach {
            assertTrue("缺少中文名: ${it.wire}", it.label.isNotBlank())
            assertTrue("缺少用途: ${it.wire}", it.description.isNotBlank())
        }
    }

    @Test
    fun `legacy names normalize to canonical intents`() {
        assertEquals(ClassroomIntent.SIMULATION, ClassroomIntentCatalog.normalize("explore"))
        assertEquals(ClassroomIntent.QUIZ, ClassroomIntentCatalog.normalize("practice"))
        assertEquals(ClassroomIntent.PBL, ClassroomIntentCatalog.normalize("project"))
        assertEquals(ClassroomIntent.REVIEW, ClassroomIntentCatalog.normalize(" REVIEW "))
        assertEquals(ClassroomIntent.ADAPTIVE, ClassroomIntentCatalog.normalize(null))
        // 旧名必须被接受，否则会破坏既有客户端
        assertTrue(ClassroomIntentCatalog.isAccepted("practice"))
        assertTrue(ClassroomIntentCatalog.isAccepted("explore"))
        assertFalse(ClassroomIntentCatalog.isAccepted("3d"))
    }

    @Test
    fun `unknown mode falls back but is not accepted`() {
        assertEquals(ClassroomIntent.ADAPTIVE, ClassroomIntentCatalog.normalize("nonsense"))
        assertFalse(ClassroomIntentCatalog.isAccepted("nonsense"))
    }

    @Test
    fun `difficulty and duration are validated against backend whitelist`() {
        assertEquals("入门", ClassroomIntentCatalog.difficultyLabel("beginner"))
        assertEquals("进阶", ClassroomIntentCatalog.difficultyLabel("advanced"))
        assertNull("非法难度不得回显", ClassroomIntentCatalog.difficultyLabel("hacker"))
        assertEquals(20, ClassroomIntentCatalog.normalizeDuration(20))
        assertNull(ClassroomIntentCatalog.normalizeDuration(5000))
        assertNull(ClassroomIntentCatalog.normalizeDuration(1))
    }

    @Test
    fun `intent note states composition is not guaranteed`() {
        assertTrue(ClassroomIntentCatalog.INTENT_NOTE.contains("生成意图"))
        assertTrue(ClassroomIntentCatalog.INTENT_NOTE.contains("决定"))
    }

    // ===== B. 进度状态机 =====

    @Test
    fun `progress phases follow backend status`() {
        assertEquals(ClassroomPhase.QUEUED, ClassroomProgressReducer.phaseOf("queued"))
        assertEquals(ClassroomPhase.RUNNING, ClassroomProgressReducer.phaseOf("running"))
        assertEquals(ClassroomPhase.SUCCEEDED, ClassroomProgressReducer.phaseOf("succeeded"))
        assertEquals(ClassroomPhase.FAILED, ClassroomProgressReducer.phaseOf("failed"))
    }

    @Test
    fun `step labels cover real magicclass steps`() {
        assertEquals("生成语音讲解", ClassroomProgressReducer.stepLabel("generating_tts"))
        assertEquals("生成教学大纲", ClassroomProgressReducer.stepLabel("generating_outlines"))
        assertEquals("保存课堂", ClassroomProgressReducer.stepLabel("persisting"))
        assertEquals("已完成", ClassroomProgressReducer.stepLabel("completed"))
        assertEquals("处理中", ClassroomProgressReducer.stepLabel("bogus"))
    }

    @Test
    fun `success without public url is reported as generated but closed`() {
        val state = ClassroomProgressState(phase = ClassroomPhase.SUCCEEDED, publicUrl = null)
        assertTrue(state.generatedButClosed)
        assertNull("没有公开地址时不得给出可打开入口", state.openableUrl())

        val openable = state.copy(publicUrl = "https://classroom.example.edu/classroom/r1")
        assertFalse(openable.generatedButClosed)
        assertEquals("https://classroom.example.edu/classroom/r1", openable.openableUrl())
    }

    @Test
    fun `internal url is never considered openable by accident`() {
        // 后端已不再下发内部地址；这里保证前端也不会把它当可打开
        val state = ClassroomProgressState(
            phase = ClassroomPhase.SUCCEEDED,
            publicUrl = "http://magicclass:3000/classroom/r1",
        )
        // openableUrl 只做"非空"判断，真正的准入由 ClassroomUrlPolicy 负责；
        // 因此这里断言 policy 会拒绝它（见 ClassroomUrlPolicyTest）。
        assertTrue(com.example.campusai.data.remote.ClassroomUrlPolicy.sanitize(
            state.openableUrl(),
            listOf("https://classroom.example.edu"),
        ) == null)
    }

    // ===== C. 真实组成 =====

    @Test
    fun `composition description uses real counts not requested mode`() {
        val dto = InteractiveClassroomCompositionDto(
            classroomId = "r1",
            sceneTotal = 4,
            scenes = listOf(
                InteractiveClassroomSceneCountDto("slide", 3),
                InteractiveClassroomSceneCountDto("quiz", 1),
            ),
            widgetTypes = emptyList(),
            hasWhiteboard = true,
        )
        val described = ClassroomCompositionText.describe(dto)!!
        assertEquals(4, described.total)
        assertEquals(2, described.parts.size)
        assertEquals(listOf("白板推导"), described.extras)
        val summary = ClassroomCompositionText.summary(described)
        assertTrue(summary.contains("幻灯片 ×3"))
        assertTrue(summary.contains("测验 ×1"))
    }

    @Test
    fun `unknown scene and widget types are shown as unknown not faked`() {
        val dto = InteractiveClassroomCompositionDto(
            sceneTotal = 1,
            scenes = listOf(InteractiveClassroomSceneCountDto("hologram", 1)),
            widgetTypes = listOf(InteractiveClassroomWidgetCountDto("quantum-sandbox", 1)),
        )
        val described = ClassroomCompositionText.describe(dto)!!
        assertEquals("未知类型（hologram）", described.parts[0].label)
        assertFalse(described.parts[0].known)
        assertEquals("未知形式（quantum-sandbox）", described.widgets[0].label)
    }

    @Test
    fun `composition read failure is reported as failure not empty classroom`() {
        val dto = InteractiveClassroomCompositionDto(sceneTotal = 0, error = "课堂响应结构异常")
        val described = ClassroomCompositionText.describe(dto)!!
        assertEquals("课堂响应结构异常", described.error)
        assertTrue(ClassroomCompositionText.summary(described).contains("课堂内容读取失败"))
    }

    @Test
    fun `3d degradation is a notice not a failure`() {
        val dto = InteractiveClassroomCompositionDto(
            sceneTotal = 1,
            widgetTypes = listOf(InteractiveClassroomWidgetCountDto("visualization3d", 1)),
            requiresExternal3d = true,
            external3dAvailable = false,
            degraded = true,
        )
        val notice = ClassroomCompositionText.threeDNotice(ClassroomCompositionText.describe(dto))!!
        assertTrue(notice.contains("无法访问外部 3D 资源"))
        assertNull(ClassroomCompositionText.threeDNotice(ClassroomCompositionText.describe(
            InteractiveClassroomCompositionDto(sceneTotal = 1)
        )))
    }

    // ===== D. CPM 异步状态机 =====

    private fun queued() = JobSnapshot(jobId = "job_1", status = "QUEUED")

    @Test
    fun `create returns queued without approval then awaits approval`() {
        var state = ClassroomJobMachine.confirmRequested(ClassroomJobState())
        assertEquals(JobPhase.CREATING_JOB, state.phase)
        state = ClassroomJobMachine.jobCreated(state, queued())
        assertEquals(JobPhase.QUEUED, state.phase)
        assertNull(state.approvalId)
        assertFalse("QUEUED 阶段不得显示批准按钮", state.canApprove)

        state = ClassroomJobMachine.pollResult(
            state,
            queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
        )
        assertEquals(JobPhase.AWAITING_APPROVAL, state.phase)
        assertEquals("apv_1", state.approvalId)
        assertTrue(state.canApprove)
    }

    @Test
    fun `approve resumes the same job and reaches success`() {
        var state = ClassroomJobMachine.jobCreated(
            ClassroomJobMachine.confirmRequested(ClassroomJobState()),
            queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
        )
        state = ClassroomJobMachine.approveRequested(state)
        assertEquals(JobPhase.APPROVING, state.phase)
        state = ClassroomJobMachine.approveDone(state, queued())
        assertEquals(JobPhase.QUEUED, state.phase)
        assertEquals("job_1", state.jobId)
        assertNull(state.approvalId)

        state = ClassroomJobMachine.pollResult(state, queued().copy(status = "RUNNING"))
        assertEquals(JobPhase.RUNNING, state.phase)

        state = ClassroomJobMachine.pollResult(
            state,
            queued().copy(
                status = "SUCCEEDED",
                sessionId = "om_1",
                deepLink = "/courses/c1?tab=mentoring&session=om_1",
            ),
        )
        assertEquals(JobPhase.SUCCEEDED, state.phase)
        assertEquals("om_1", state.sessionId)
        assertTrue(state.isTerminal)
        assertFalse(state.awaitingOutcome)
    }

    @Test
    fun `success without deep link keeps waiting`() {
        val state = ClassroomJobMachine.pollResult(
            ClassroomJobMachine.jobCreated(ClassroomJobMachine.confirmRequested(ClassroomJobState()), queued()),
            queued().copy(status = "SUCCEEDED"),
        )
        assertEquals(JobPhase.SUCCEEDED, state.phase)
        assertTrue("缺深链时不得提前宣布完成", state.awaitingOutcome)
    }

    @Test
    fun `duplicate confirm and approve are rejected`() {
        val creating = ClassroomJobMachine.confirmRequested(ClassroomJobState())
        assertEquals(creating, ClassroomJobMachine.confirmRequested(creating))

        val approving = ClassroomJobMachine.approveRequested(
            ClassroomJobMachine.jobCreated(
                ClassroomJobMachine.confirmRequested(ClassroomJobState()),
                queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
            ),
        )
        assertEquals(approving, ClassroomJobMachine.approveRequested(approving))
    }

    @Test
    fun `stale snapshot does not regress running back to awaiting approval`() {
        var state = ClassroomJobMachine.jobCreated(
            ClassroomJobMachine.confirmRequested(ClassroomJobState()),
            queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
        )
        state = ClassroomJobMachine.approveDone(state, queued())
        state = ClassroomJobMachine.pollResult(state, queued().copy(status = "RUNNING"))
        state = ClassroomJobMachine.pollResult(
            state,
            queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
        )
        assertEquals(JobPhase.RUNNING, state.phase)
    }

    @Test
    fun `reject and expire end in explicit non success states`() {
        val awaiting = ClassroomJobMachine.jobCreated(
            ClassroomJobMachine.confirmRequested(ClassroomJobState()),
            queued().copy(status = "AWAITING_APPROVAL", pendingApprovalId = "apv_1"),
        )
        assertEquals(JobPhase.REJECTED, ClassroomJobMachine.approveRejected(awaiting).phase)
        assertEquals(JobPhase.EXPIRED, ClassroomJobMachine.approveFailed(awaiting, "过期", expired = true).phase)
        assertEquals(
            JobPhase.AWAITING_APPROVAL,
            ClassroomJobMachine.approveFailed(awaiting, "网络错误").phase,
        )
    }

    @Test
    fun `restored state reuses the same job and forbids re creating`() {
        val restored = ClassroomJobMachine.restored("job_9")
        assertEquals("job_9", restored.jobId)
        assertTrue(restored.created)
        assertFalse("恢复后不得再显示『确认生成』", restored.canConfirm)
    }

    @Test
    fun `network failure does not change a settled phase`() {
        var state = ClassroomJobMachine.jobCreated(
            ClassroomJobMachine.confirmRequested(ClassroomJobState()),
            queued().copy(status = "RUNNING"),
        )
        state = ClassroomJobMachine.pollFailed(state, "网络断开")
        assertEquals(JobPhase.RUNNING, state.phase)
        assertTrue(state.error.contains("网络断开"))
    }
}

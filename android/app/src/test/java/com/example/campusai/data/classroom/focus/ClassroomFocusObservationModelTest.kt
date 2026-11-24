package com.example.campusai.data.classroom.focus

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomFocusObservationModelTest {
    private fun feed(
        state: ClassroomFocusState,
        fromMs: Long,
        toMs: Long,
        faceCount: Int,
        yawDegrees: Double? = null,
        pitchDegrees: Double? = null,
        stage: String? = null,
    ): ClassroomFocusState {
        var next = state
        var at = fromMs
        while (at <= toMs) {
            next = ClassroomFocusObservation.applySample(
                state = next,
                atMs = at,
                faceCount = faceCount,
                yawDegrees = yawDegrees,
                pitchDegrees = pitchDegrees,
                stage = stage,
                sessionId = next.sessionId,
            )
            at += ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS
        }
        return next
    }

    private fun feedInvalid(
        state: ClassroomFocusState,
        fromMs: Long,
        toMs: Long,
        reason: ClassroomFocusReason,
    ): ClassroomFocusState {
        var next = state
        var at = fromMs
        while (at <= toMs) {
            next = ClassroomFocusObservation.applySample(
                state = next,
                atMs = at,
                faceCount = 0,
                valid = false,
                invalidReason = reason,
                sessionId = next.sessionId,
            )
            at += ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS
        }
        return next
    }

    @Test
    fun `engineering windows are centralized at four hertz and ten seconds`() {
        assertEquals(250L, ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS)
        assertEquals(10_000L, ClassroomFocusObservationConfig.WINDOW_MS)
        assertEquals(
            4.0,
            1_000.0 / ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS,
            0.0,
        )
        assertEquals(40, (ClassroomFocusObservationConfig.WINDOW_MS /
            ClassroomFocusObservationConfig.SAMPLE_INTERVAL_MS).toInt())
    }

    @Test
    fun `public labels keep unavailable wording and reason`() {
        assertEquals(
            listOf("正在观察", "近期有课堂操作", "检测到人脸", "无法判断", "无法判断"),
            ClassroomFocusStatus.entries.map { it.label },
        )
        assertEquals("画面太暗，暂时无法判断", ClassroomFocusReason.LOW_LIGHT.label)
        assertEquals("摄像头被其他应用占用", ClassroomFocusReason.CAMERA_BUSY.label)
    }

    @Test
    fun `window closes exactly at ten seconds and boundary event stays in closing window`() {
        var state = ClassroomFocusObservation.begin(0)
        state = feed(state, 0, 9_750, faceCount = 1, yawDegrees = -3.0, pitchDegrees = -6.0, stage = "slide")
        assertTrue(state.windows.isEmpty())

        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 9_999,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.SUBMIT_ANSWER, 10_000,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.ASK_QUESTION, 10_001,
        )
        state = ClassroomFocusObservation.applySample(
            state = state,
            atMs = 10_000,
            faceCount = 1,
            yawDegrees = -3.0,
            pitchDegrees = -6.0,
            stage = "slide",
            sessionId = state.sessionId,
        )

        assertEquals(1, state.windows.size)
        val window = state.windows.single()
        assertEquals(0, window.index)
        assertEquals(0L, window.startOffsetMs)
        assertEquals(10_000L, window.endOffsetMs)
        assertTrue(window.complete)
        assertEquals(40, window.validSampleCount)
        assertEquals(40, window.faceVisibleSampleCount)
        assertEquals(1.0, window.faceVisibleRatio, 0.0001)
        assertEquals(40, window.yaw?.samples)
        assertEquals(-3.0, window.yaw?.mean ?: 99.0, 0.0001)
        assertEquals(-6.0, window.pitch?.mean ?: 99.0, 0.0001)
        assertEquals("slide", window.dominantStage)
        assertEquals(ClassroomObservationVerdict.OBSERVABLE, window.verdict)
        assertNull(window.unavailableReason)
        assertEquals(1, window.manualPageTurns)
        assertEquals(1, window.quizSubmissions)
        assertEquals(0, window.questions)

        // 边界只归属一个窗口：10_000 属于窗口 0，10_001 进入窗口 1，不重复计数。
        state = ClassroomFocusObservation.applySample(
            state = state,
            atMs = 20_000,
            faceCount = 1,
            sessionId = state.sessionId,
        )
        assertEquals(2, state.windows.size)
        assertEquals(0, state.windows[1].manualPageTurns)
        assertEquals(0, state.windows[1].quizSubmissions)
        assertEquals(1, state.windows[1].questions)
    }

    @Test
    fun `events after judgement cutoff never enter earlier window`() {
        var state = feed(ClassroomFocusObservation.begin(0), 0, 9_750, faceCount = 1)
        state = ClassroomFocusObservation.applySample(
            state, 10_000, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(0, state.windows.single().manualPageTurns)

        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 10_500,
        )
        state = ClassroomFocusObservation.applySample(
            state, 10_250, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(0, state.windows.single().manualPageTurns)

        state = feed(state, 10_500, 19_750, faceCount = 1)
        state = ClassroomFocusObservation.applySample(
            state, 20_000, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(2, state.windows.size)
        assertEquals(0, state.windows[0].manualPageTurns)
        assertEquals(1, state.windows[1].manualPageTurns)
    }

    @Test
    fun `invalid frames produce unobservable window with low light reason`() {
        var state = feedInvalid(
            ClassroomFocusObservation.begin(0),
            fromMs = 0,
            toMs = 9_750,
            reason = ClassroomFocusReason.LOW_LIGHT,
        )
        state = ClassroomFocusObservation.applySample(
            state = state,
            atMs = 10_000,
            faceCount = 0,
            valid = false,
            invalidReason = ClassroomFocusReason.LOW_LIGHT,
            sessionId = state.sessionId,
        )
        val window = state.windows.single()
        assertEquals(0, window.validSampleCount)
        assertEquals(40, window.invalidSampleCount)
        assertEquals(40, window.reasonCounts[ClassroomFocusReason.LOW_LIGHT])
        assertEquals(ClassroomObservationVerdict.UNOBSERVABLE, window.verdict)
        assertEquals(ClassroomFocusReason.LOW_LIGHT, window.unavailableReason)
        assertEquals(
            ClassroomFocusStatus.UNAVAILABLE,
            ClassroomFocusObservation.statusOf(state, 10_000),
        )
    }

    @Test
    fun `no face and multiple faces are unobservable with distinct reasons`() {
        var noFace = feed(ClassroomFocusObservation.begin(0), 0, 9_750, faceCount = 0)
        noFace = ClassroomFocusObservation.applySample(
            noFace, 10_000, faceCount = 0, sessionId = noFace.sessionId,
        )
        val noFaceWindow = noFace.windows.single()
        assertEquals(40, noFaceWindow.validSampleCount)
        assertEquals(0, noFaceWindow.faceVisibleSampleCount)
        assertEquals(ClassroomFocusReason.NO_FACE, noFaceWindow.unavailableReason)
        assertEquals(
            ClassroomFocusStatus.FACE_MISSING,
            ClassroomFocusObservation.statusOf(noFace, 10_000),
        )
        assertEquals(
            ClassroomFocusReason.NO_FACE,
            ClassroomFocusObservation.reasonOf(noFace, 10_000),
        )

        var multiple = feed(ClassroomFocusObservation.begin(0), 0, 9_750, faceCount = 2)
        multiple = ClassroomFocusObservation.applySample(
            multiple, 10_000, faceCount = 2, sessionId = multiple.sessionId,
        )
        val multipleWindow = multiple.windows.single()
        assertEquals(40, multipleWindow.invalidSampleCount)
        assertEquals(ClassroomFocusReason.MULTIPLE_FACES, multipleWindow.unavailableReason)
        assertEquals(
            ClassroomFocusReason.MULTIPLE_FACES,
            ClassroomFocusObservation.reasonOf(multiple, 10_000),
        )
    }

    @Test
    fun `sampling gap records skipped windows instead of hiding them`() {
        var state = ClassroomFocusObservation.begin(0)
        state = ClassroomFocusObservation.applySample(
            state, 0, faceCount = 1, sessionId = state.sessionId,
        )
        state = ClassroomFocusObservation.applySample(
            state, 30_000, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(3, state.windows.size)
        assertEquals(ClassroomFocusReason.INSUFFICIENT_SAMPLES, state.windows[0].unavailableReason)
        assertEquals(ClassroomFocusReason.SAMPLING_INTERRUPTED, state.windows[1].unavailableReason)
        assertEquals(ClassroomFocusReason.SAMPLING_INTERRUPTED, state.windows[2].unavailableReason)
    }

    @Test
    fun `automatic and replay events are excluded while manual events count`() {
        var state = ClassroomFocusObservation.begin(0)
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 1_000,
            source = ClassroomFocusEventSource.AUTOMATIC,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 1_250,
            source = ClassroomFocusEventSource.REPLAY,
        )
        assertTrue(state.events.isEmpty())
        assertNull(state.lastActivityAtMs)

        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 2_000,
        )
        assertEquals(1, state.events.size)
        assertEquals(ClassroomFocusEventSource.STUDENT, state.events.single().source)
        assertEquals(ClassroomFocusStatus.RECENT_ACTIVITY, ClassroomFocusObservation.statusOf(state, 2_000))
    }

    @Test
    fun `closing and reopening resets windows and ignores old session callbacks`() {
        var old = ClassroomFocusObservation.begin(0, sessionId = 1)
        old = feed(old, 0, 2_000, faceCount = 1)
        assertEquals(1L, old.sessionId)
        assertEquals(ClassroomFocusState(), ClassroomFocusObservation.stop())

        val fresh = ClassroomFocusObservation.begin(5_000, sessionId = 2)
        val ignored = ClassroomFocusObservation.applySample(
            state = fresh,
            atMs = 5_250,
            faceCount = 1,
            sessionId = 1,
        )
        assertEquals(fresh, ignored)
        assertTrue(fresh.windows.isEmpty())

        val accepted = ClassroomFocusObservation.applySample(
            state = fresh,
            atMs = 5_250,
            faceCount = 1,
            sessionId = 2,
        )
        assertEquals(1, accepted.currentWindow?.validSamples)
    }

    @Test
    fun `session gate rejects closed generation after reopen`() {
        val gate = ClassroomObservationSessionGate()
        val old = gate.open()
        assertTrue(gate.isCurrent(old))
        gate.close()
        assertFalse(gate.isCurrent(old))
        val fresh = gate.open()
        assertFalse(gate.isCurrent(old))
        assertTrue(gate.isCurrent(fresh))
        gate.close()
        assertFalse(gate.isCurrent(fresh))
    }

    @Test
    fun `head statistics and partial window export keep facts`() {
        var state = ClassroomFocusObservation.begin(0)
        val yaw = listOf(-10.0, -5.0, 0.0, 5.0, 10.0)
        yaw.forEachIndexed { index, value ->
            state = ClassroomFocusObservation.applySample(
                state = state,
                atMs = index * 250L,
                faceCount = 1,
                yawDegrees = value,
                pitchDegrees = value / 2,
                stage = "quiz",
                sessionId = state.sessionId,
            )
        }
        val window = ClassroomFocusObservation.windowsForExport(state, 1_000).single()
        assertFalse(window.complete)
        assertEquals(0L, window.startOffsetMs)
        assertEquals(1_000L, window.endOffsetMs)
        assertEquals(5, window.validSampleCount)
        assertEquals(5, window.yaw?.samples)
        assertEquals(0.0, window.yaw?.mean ?: 99.0, 0.0001)
        assertEquals(7.071, window.yaw?.standardDeviation ?: 0.0, 0.001)
        assertEquals(-10.0, window.yaw?.min ?: 0.0, 0.0001)
        assertEquals(10.0, window.yaw?.max ?: 0.0, 0.0001)
        assertEquals("quiz", window.dominantStage)
        assertEquals(ClassroomObservationVerdict.OBSERVABLE, window.verdict)
    }

    @Test
    fun `sustained no face turns confirmed face into unavailable status`() {
        var state = feed(ClassroomFocusObservation.begin(0), 0, 2_000, faceCount = 1)
        assertEquals(ClassroomFocusStatus.FACE_PRESENT, ClassroomFocusObservation.statusOf(state, 2_000))
        state = feed(state, 2_000, 13_750, faceCount = 0)
        assertEquals(ClassroomFocusStatus.FACE_PRESENT, ClassroomFocusObservation.statusOf(state, 13_750))
        state = ClassroomFocusObservation.applySample(
            state, 14_000, faceCount = 0, sessionId = state.sessionId,
        )
        assertEquals(ClassroomFocusStatus.FACE_MISSING, ClassroomFocusObservation.statusOf(state, 14_000))
        assertEquals(ClassroomFocusReason.NO_FACE, ClassroomFocusObservation.reasonOf(state, 14_000))
    }

    @Test
    fun `page turns every eight seconds never reset the no-face timer`() {
        // 先确认人脸，随后持续无脸；每 8 秒一次主动翻页。
        var state = feed(ClassroomFocusObservation.begin(0), 0, 2_000, faceCount = 1)
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 10_000,
        )
        state = feed(state, 2_250, 13_750, faceCount = 0)
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 16_000,
        )
        state = feed(state, 14_000, 18_000, faceCount = 0)

        // 翻页是独立事实，不能把连续无脸计时清回 0；达到 12 秒后必须仍为「无法判断」。
        assertEquals(
            ClassroomFocusStatus.FACE_MISSING,
            ClassroomFocusObservation.statusOf(state, 18_000),
        )
        assertEquals(
            ClassroomFocusReason.NO_FACE,
            ClassroomFocusObservation.reasonOf(state, 18_000),
        )
    }

    @Test
    fun `activity after face missing stays a fact without replacing the verdict`() {
        var state = feed(ClassroomFocusObservation.begin(0), 0, 2_000, faceCount = 1)
        state = feed(state, 2_250, 14_250, faceCount = 0)
        assertEquals(
            ClassroomFocusStatus.FACE_MISSING,
            ClassroomFocusObservation.statusOf(state, 14_250),
        )

        // 已经进入「无法判断」后再次翻页/交卷/提问，状态与原因不得被近期操作覆盖。
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 14_250,
        )
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.SUBMIT_ANSWER, 14_750,
        )
        assertEquals(
            ClassroomFocusStatus.FACE_MISSING,
            ClassroomFocusObservation.statusOf(state, 15_000),
        )
        assertEquals(
            ClassroomFocusReason.NO_FACE,
            ClassroomFocusObservation.reasonOf(state, 15_000),
        )
        assertEquals(14_750L, state.lastActivityAtMs)

        // 近期操作作为独立事实保留在窗口计数里，直到窗口封口。
        state = feed(state, 15_000, 19_750, faceCount = 0)
        state = ClassroomFocusObservation.applySample(
            state, 20_000, faceCount = 0, sessionId = state.sessionId,
        )
        val window = state.windows.last()
        assertEquals(1, window.index)
        assertEquals(ClassroomObservationVerdict.UNOBSERVABLE, window.verdict)
        assertEquals(ClassroomFocusReason.NO_FACE, window.unavailableReason)
        assertEquals(1, window.manualPageTurns)
        assertEquals(1, window.quizSubmissions)
        assertEquals(0, window.questions)
    }

    @Test
    fun `late event after a window closes never rewrites that window`() {
        var state = feed(ClassroomFocusObservation.begin(0), 0, 9_750, faceCount = 1)
        state = ClassroomFocusObservation.applySample(
            state, 10_000, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(0, state.windows.single().manualPageTurns)

        // 操作发生在窗口 0 内，但直到窗口封口后才到达：已发布窗口是快照，不回填。
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.PAGE_TURN, 2_000,
        )
        assertEquals(0, state.windows.single().manualPageTurns)
        assertEquals(1, state.events.size)

        // 继续推进时，事件也不能倒灌进后续窗口。
        state = feed(state, 10_250, 19_750, faceCount = 1)
        state = ClassroomFocusObservation.applySample(
            state, 20_000, faceCount = 1, sessionId = state.sessionId,
        )
        assertEquals(2, state.windows.size)
        assertEquals(0, state.windows[0].manualPageTurns)
        assertEquals(0, state.windows[1].manualPageTurns)
    }

    @Test
    fun `invalid signal keeps recent activity facts for export`() {
        var state = feed(ClassroomFocusObservation.begin(0), 0, 1_000, faceCount = 1)
        state = ClassroomFocusObservation.recordEvent(
            state, ClassroomFocusEventType.ASK_QUESTION, 1_250,
        )
        state = ClassroomFocusObservation.applySample(
            state = state,
            atMs = 1_500,
            faceCount = 0,
            valid = false,
            invalidReason = ClassroomFocusReason.LOW_LIGHT,
            sessionId = state.sessionId,
        )
        assertEquals(ClassroomFocusStatus.UNAVAILABLE, ClassroomFocusObservation.statusOf(state, 1_500))
        assertEquals(1_250L, state.lastActivityAtMs)
        assertEquals(1, state.events.size)
    }

    @Test
    fun `window history is bounded`() {
        var state = ClassroomFocusObservation.begin(0)
        repeat(ClassroomFocusObservationConfig.WINDOW_HISTORY_LIMIT + 3) { window ->
            state = feed(
                state,
                fromMs = window * ClassroomFocusObservationConfig.WINDOW_MS,
                toMs = window * ClassroomFocusObservationConfig.WINDOW_MS + 9_750,
                faceCount = 1,
            )
            state = ClassroomFocusObservation.applySample(
                state = state,
                atMs = (window + 1) * ClassroomFocusObservationConfig.WINDOW_MS,
                faceCount = 1,
                sessionId = state.sessionId,
            )
        }
        assertEquals(
            ClassroomFocusObservationConfig.WINDOW_HISTORY_LIMIT,
            state.windows.size,
        )
    }
}

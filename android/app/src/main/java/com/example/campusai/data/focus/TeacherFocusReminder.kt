package com.example.campusai.data.focus

import com.example.campusai.data.behavior.BehaviorDisplayState
import com.example.campusai.data.behavior.PresenceState
import com.example.campusai.data.behavior.StudyBehavior

/** 老师式提醒的种类；只描述可观察行为，不推断心理或学习效果。 */
enum class TeacherReminderKind {
    PHONE,
    NO_STUDY,
    LOOK_AWAY,
    DROWSY,
    ABSENT,
    RECOVERED,
}

enum class TeacherReminderTone {
    GENTLE,
    FIRM,
    CARE,
    PRAISE,
}

data class TeacherReminder(
    val kind: TeacherReminderKind,
    val tone: TeacherReminderTone,
    val title: String,
    val message: String,
    val spokenText: String,
    val createdAtMs: Long,
    val occurrence: Int,
)

data class TeacherReminderConfig(
    val phoneTriggerMs: Long = 4_000,
    val noStudyTriggerMs: Long = 18_000,
    val lookAwayTriggerMs: Long = 10_000,
    val drowsyTriggerMs: Long = 8_000,
    val absentTriggerMs: Long = 8_000,
    val recoveryTriggerMs: Long = 10_000,
    val globalCooldownMs: Long = 45_000,
    val kindCooldownMs: Long = 3 * 60_000,
    val recoveryCooldownMs: Long = 5 * 60_000,
    val maxPerSession: Int = 8,
)

/**
 * 把端侧已有的学习行为/在席/表情观察翻译成“老师提醒”。
 *
 * 设计约束：
 * - 只在异常持续到阈值后提醒，避免一次误判就打断；
 * - 同类提醒 3 分钟冷却、全局 45 秒冷却、每堂最多 8 次；
 * - 同一类重复发生时逐步换成更明确的说法，但绝不下诊断；
 * - 恢复到学习状态后给一次表扬，让提醒不是单向的批评。
 */
class TeacherFocusReminderEngine(
    private val config: TeacherReminderConfig = TeacherReminderConfig(),
) {
    private val activeSince = mutableMapOf<TeacherReminderKind, Long>()
    private val occurrence = mutableMapOf<TeacherReminderKind, Int>()
    private val lastAt = mutableMapOf<TeacherReminderKind, Long>()
    private var lastReminderAt: Long? = null
    private var lastRecoveryAt: Long? = null
    private var studySince: Long? = null
    private var total = 0
    private var lastKind: TeacherReminderKind? = null

    fun observe(
        displayState: BehaviorDisplayState?,
        presence: PresenceState,
        focusState: FocusState,
        timestampMs: Long,
    ): TeacherReminder? {
        val kind = currentKind(displayState, presence, focusState)
        updateActiveTimers(kind, timestampMs)

        if (kind == null) {
            studySince = if (isStudying(displayState)) studySince ?: timestampMs else null
            if (
                isStudying(displayState) &&
                lastKind != null &&
                lastKind != TeacherReminderKind.RECOVERED &&
                studySince != null &&
                timestampMs - studySince!! >= config.recoveryTriggerMs &&
                (lastRecoveryAt == null || timestampMs - lastRecoveryAt!! >= config.recoveryCooldownMs)
            ) {
                lastRecoveryAt = timestampMs
                lastKind = TeacherReminderKind.RECOVERED
                return build(TeacherReminderKind.RECOVERED, timestampMs)
            }
            return null
        }
        studySince = null
        if (!shouldRemind(kind, timestampMs)) return null
        val elapsed = timestampMs - (activeSince[kind] ?: return null)
        if (elapsed < triggerMs(kind)) return null

        lastReminderAt = timestampMs
        lastAt[kind] = timestampMs
        lastKind = kind
        total += 1
        occurrence[kind] = (occurrence[kind] ?: 0) + 1
        return build(kind, timestampMs)
    }

    fun reset() {
        activeSince.clear()
        occurrence.clear()
        lastAt.clear()
        lastReminderAt = null
        lastRecoveryAt = null
        studySince = null
        total = 0
        lastKind = null
    }

    private fun updateActiveTimers(kind: TeacherReminderKind?, timestampMs: Long) {
        if (kind == null) {
            activeSince.clear()
            return
        }
        TeacherReminderKind.entries.forEach { candidate ->
            if (candidate == kind) {
                activeSince.putIfAbsent(candidate, timestampMs)
            } else {
                activeSince.remove(candidate)
            }
        }
    }

    private fun shouldRemind(kind: TeacherReminderKind, timestampMs: Long): Boolean {
        if (total >= config.maxPerSession) return false
        lastReminderAt?.let { if (timestampMs - it < config.globalCooldownMs) return false }
        lastAt[kind]?.let { if (timestampMs - it < config.kindCooldownMs) return false }
        return true
    }

    private fun triggerMs(kind: TeacherReminderKind): Long = when (kind) {
        TeacherReminderKind.PHONE -> config.phoneTriggerMs
        TeacherReminderKind.NO_STUDY -> config.noStudyTriggerMs
        TeacherReminderKind.LOOK_AWAY -> config.lookAwayTriggerMs
        TeacherReminderKind.DROWSY -> config.drowsyTriggerMs
        TeacherReminderKind.ABSENT -> config.absentTriggerMs
        TeacherReminderKind.RECOVERED -> config.recoveryTriggerMs
    }

    private fun currentKind(
        displayState: BehaviorDisplayState?,
        presence: PresenceState,
        focusState: FocusState,
    ): TeacherReminderKind? {
        if (presence == PresenceState.ABSENT || focusState == FocusState.NO_FACE) {
            return TeacherReminderKind.ABSENT
        }
        if (displayState is BehaviorDisplayState.Stable) {
            return when (displayState.behavior) {
                StudyBehavior.PHONE_USE, StudyBehavior.PHONE_PICKUP -> TeacherReminderKind.PHONE
                StudyBehavior.LOOKING_AWAY -> TeacherReminderKind.LOOK_AWAY
                StudyBehavior.DROWSY, StudyBehavior.SLEEPING, StudyBehavior.HEAD_DOWN ->
                    TeacherReminderKind.DROWSY
                StudyBehavior.IDLE -> TeacherReminderKind.NO_STUDY
                else -> if (focusState == FocusState.BREAK_SUGGESTED) {
                    TeacherReminderKind.DROWSY
                } else null
            }
        }
        return if (focusState == FocusState.BREAK_SUGGESTED) TeacherReminderKind.DROWSY else null
    }

    private fun isStudying(displayState: BehaviorDisplayState?): Boolean =
        displayState is BehaviorDisplayState.Stable && when (displayState.behavior) {
            StudyBehavior.VISIBLE_STUDY,
            StudyBehavior.READING,
            StudyBehavior.WRITING,
            StudyBehavior.COMPUTER,
            StudyBehavior.TYPING -> true
            else -> false
        }

    private fun build(kind: TeacherReminderKind, timestampMs: Long): TeacherReminder {
        val count = occurrence[kind] ?: 1
        val tone = when (kind) {
            TeacherReminderKind.PHONE, TeacherReminderKind.NO_STUDY ->
                if (count >= 2) TeacherReminderTone.FIRM else TeacherReminderTone.GENTLE
            TeacherReminderKind.LOOK_AWAY -> TeacherReminderTone.GENTLE
            TeacherReminderKind.DROWSY, TeacherReminderKind.ABSENT -> TeacherReminderTone.CARE
            TeacherReminderKind.RECOVERED -> TeacherReminderTone.PRAISE
        }
        val title = when (tone) {
            TeacherReminderTone.GENTLE -> "小伴老师提醒"
            TeacherReminderTone.FIRM -> "小伴老师再提醒一次"
            TeacherReminderTone.CARE -> "小伴老师关心你"
            TeacherReminderTone.PRAISE -> "小伴老师看到你了"
        }
        val message = textFor(kind, count)
        return TeacherReminder(
            kind = kind,
            tone = tone,
            title = title,
            message = message,
            spokenText = message,
            createdAtMs = timestampMs,
            occurrence = count,
        )
    }

    private fun textFor(kind: TeacherReminderKind, count: Int): String {
        val variants = when (kind) {
            TeacherReminderKind.PHONE -> listOf(
                "手机先放一放，我们把这一页看完。老师在这儿陪着你。",
                "又摸到手机啦。把它翻过去，注意力回到当前任务上。",
                "老师再提醒一次：这一小段先不刷手机，结束后再处理。",
            )
            TeacherReminderKind.NO_STUDY -> listOf(
                "老师看到你停下来了。先回到当前任务，做五分钟就顺了。",
                "别让思绪飘太远。把下一步写下来，然后开始。",
                "已经停了一会儿了。我们只做眼前这一小步，老师陪着你。",
            )
            TeacherReminderKind.LOOK_AWAY -> listOf(
                "视线回到书本或屏幕上，老师和你一起看这一页。",
                "看回当前这一行，别让注意力跑远。",
            )
            TeacherReminderKind.DROWSY -> listOf(
                "是不是有点困了？站起来喝口水，回来我们继续。",
                "眼睛快闭上了。先活动一下，再坚持这一小段。",
            )
            TeacherReminderKind.ABSENT -> listOf(
                "你离开了一会儿。回来后告诉我一声，老师给你留着进度。",
                "老师暂时看不到你了。如果在，回到座位继续；如果不在，先暂停。",
            )
            TeacherReminderKind.RECOVERED -> listOf(
                "很好，老师看到你回来了。保持这个状态，继续。",
            )
        }
        return variants[(count - 1).coerceAtLeast(0).coerceAtMost(variants.lastIndex)]
    }
}

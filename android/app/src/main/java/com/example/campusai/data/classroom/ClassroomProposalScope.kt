package com.example.campusai.data.classroom

import androidx.lifecycle.SavedStateHandle
import com.example.campusai.data.remote.agent.InteractiveClassroomProposalDto

/**
 * CPM 互动课堂提案的**作用域**：指纹 + 可持久化的恢复记录。
 *
 * 为什么需要它：修复前 `acceptClassroomProposal()` 只替换 proposal，
 * 既不清空 `classroomJob`、也不取消轮询、更不动 SavedStateHandle 里的
 * jobId / idempotencyKey。于是：
 *
 *  - 第一次成功后收到第二个提案 → 界面继续显示上一节课的深链；
 *  - 第一次失败后收到第二个提案 → 复用旧幂等键，拿到旧响应或 409；
 *  - 进程重建后恢复出的是**上一个提案**的 job。
 *
 * 现在：每个提案有稳定 fingerprint；恢复记录是**一个**结构化单元，
 * 读/写/清除都以整体为单位，不会出现"只更新了一半"的错位状态。
 */
object ClassroomProposalScope {

    /**
     * 提案指纹：身份 + 提案唯一身份（服务端 nonce）+ 课程 + 模式。
     *
     * 旧后端不下发 `proposal_id` 时退化为内容指纹 —— 至少不会跨课程 / 跨模式串状态，
     * 而且**绝不会**把两个不同课程或不同模式的提案当成同一个。
     */
    fun fingerprint(identity: String, proposal: InteractiveClassroomProposalDto): String =
        fingerprint(identity, proposal.courseId, proposal.mode, proposal.proposalId)

    fun fingerprint(
        identity: String,
        courseId: String,
        mode: String,
        proposalId: String,
    ): String = listOf(
        identity.ifBlank { "anon" },
        courseId,
        mode.ifBlank { "adaptive" },
        proposalId,
    ).joinToString("|")
}

/**
 * SavedStateHandle 里的结构化恢复记录。
 *
 * 字段统一加前缀，读写永远以整体为单位：任何字段缺失都视为"没有记录"，
 * 因此不会出现"恢复了 jobId 却用了别的提案的幂等键"这种错位。
 */
data class ClassroomRestoreRecord(
    val fingerprint: String,
    val identity: String,
    val courseId: String,
    val mode: String,
    val jobId: String? = null,
    val idempotencyKey: String,
    /** 持久化的阶段名（JobPhase.name）；进程重建后据此判断能否续跑。 */
    val phase: String = JobPhase.IDLE.name,
) {
    fun withJob(jobId: String): ClassroomRestoreRecord = copy(jobId = jobId)

    /** 该记录是否属于给定的提案指纹（否则必须整体丢弃，绝不复用）。 */
    fun belongsTo(fingerprint: String): Boolean = this.fingerprint == fingerprint

    fun writeTo(handle: SavedStateHandle) {
        handle[KEY_FINGERPRINT] = fingerprint
        handle[KEY_IDENTITY] = identity
        handle[KEY_COURSE_ID] = courseId
        handle[KEY_MODE] = mode
        handle[KEY_JOB_ID] = jobId
        handle[KEY_IDEMPOTENCY] = idempotencyKey
        handle[KEY_PHASE] = phase
    }

    companion object {
        const val KEY_FINGERPRINT = "cpm_classroom_fingerprint"
        const val KEY_IDENTITY = "cpm_classroom_identity"
        const val KEY_COURSE_ID = "cpm_classroom_course_id"
        const val KEY_MODE = "cpm_classroom_mode"
        const val KEY_JOB_ID = "cpm_classroom_job_id"
        const val KEY_IDEMPOTENCY = "cpm_classroom_idempotency_key"
        const val KEY_PHASE = "cpm_classroom_phase"

        private val ALL_KEYS = listOf(
            KEY_FINGERPRINT, KEY_IDENTITY, KEY_COURSE_ID, KEY_MODE,
            KEY_JOB_ID, KEY_IDEMPOTENCY, KEY_PHASE,
        )

        /** 读取恢复记录；任一必需字段缺失即视为"没有记录"（不猜测、不部分恢复）。 */
        fun read(handle: SavedStateHandle): ClassroomRestoreRecord? {
            val fingerprint = handle.get<String>(KEY_FINGERPRINT)?.takeIf { it.isNotBlank() }
                ?: return null
            val courseId = handle.get<String>(KEY_COURSE_ID)?.takeIf { it.isNotBlank() }
                ?: return null
            val mode = handle.get<String>(KEY_MODE)?.takeIf { it.isNotBlank() } ?: return null
            val idempotencyKey = handle.get<String>(KEY_IDEMPOTENCY)?.takeIf { it.isNotBlank() }
                ?: return null
            return ClassroomRestoreRecord(
                fingerprint = fingerprint,
                identity = handle.get<String>(KEY_IDENTITY).orEmpty(),
                courseId = courseId,
                mode = mode,
                jobId = handle.get<String>(KEY_JOB_ID)?.takeIf { it.isNotBlank() },
                idempotencyKey = idempotencyKey,
                phase = handle.get<String>(KEY_PHASE)?.takeIf { it.isNotBlank() }
                    ?: JobPhase.IDLE.name,
            )
        }

        /** 整体清除：绝不留下半个记录。 */
        fun clearFrom(handle: SavedStateHandle) {
            ALL_KEYS.forEach { handle.remove<String>(it) }
        }

        /** 身份变化（登录 / 登出 / 换账号）时整体清除。 */
        fun clearIfIdentityChanged(handle: SavedStateHandle, identity: String): Boolean {
            val record = read(handle) ?: return false
            if (record.identity == identity) return false
            clearFrom(handle)
            return true
        }
    }
}

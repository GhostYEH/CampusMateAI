package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.FocusPlan
import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.TaskBreakdownRequest
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Stores accepted task plans locally so step progress survives process recreation. */
class FocusPlanRepository(
    private val storage: KeyValueStorage,
    private val api: ApiService? = null,
    private val accountKey: () -> String = { "default" },
) {
    private companion object {
        const val KEY_PREFIX = "focus_plans_v1_"
    }

    private val mutex = Mutex()
    private val _plans = MutableStateFlow<Map<String, FocusPlan>>(emptyMap())
    val plans: StateFlow<Map<String, FocusPlan>> = _plans.asStateFlow()
    private val adapter = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()
        .adapter<List<FocusPlan>>(Types.newParameterizedType(List::class.java, FocusPlan::class.java))
    private var loadedKey: String? = null

    suspend fun load() = mutex.withLock {
        ensureLoaded()
    }

    suspend fun getPlan(taskId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        _plans.value[taskId]
    }

    suspend fun savePlan(plan: FocusPlan) = mutex.withLock {
        ensureLoaded()
        persist(_plans.value + (plan.taskId to plan))
    }

    suspend fun ensurePlan(
        taskId: String,
        taskTitle: String,
        goal: String,
    ): Result<FocusPlan> = runCatching {
        require(taskId.isNotBlank()) { "任务 ID 不能为空" }
        val expectedStorageKey = storageKey()
        val existing = getPlan(taskId)
        if (existing != null) return@runCatching existing
        val service = checkNotNull(api) { "任务规划服务不可用" }
        val response = service.breakdownStudyTask(
            TaskBreakdownRequest(task_id = taskId, goal = goal.ifBlank { taskTitle }),
        )
        check(response.isSuccessful) { "无法生成任务规划(${response.code()})" }
        val body = checkNotNull(response.body()) { "任务规划响应为空" }
        check(body.steps.isNotEmpty()) { "任务规划没有可执行步骤" }
        val plan = body.toFocusPlan(taskId = taskId, taskTitle = taskTitle)
        mutex.withLock {
            ensureLoaded()
            check(loadedKey == expectedStorageKey) { "账号已切换，请重新生成任务规划" }
            persist(_plans.value + (plan.taskId to plan))
        }
        plan
    }

    suspend fun completeCurrentStep(taskId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        val current = _plans.value[taskId] ?: return@withLock null
        if (current.currentStep == null) return@withLock current
        val updated = current.completeCurrentStep()
        persist(_plans.value + (taskId to updated))
        updated
    }

    suspend fun prepareStepCompletion(taskId: String, sessionId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        val current = _plans.value[taskId] ?: return@withLock null
        val currentStep = current.currentStep ?: return@withLock null
        val updated = current.copy(
            pendingStepCompletionSessionId = sessionId,
            pendingStepCompletionStepNumber = currentStep.stepNumber,
        )
        persist(_plans.value + (taskId to updated))
        updated
    }

    suspend fun discardPreparedCompletion(taskId: String, sessionId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        val current = _plans.value[taskId] ?: return@withLock null
        if (current.pendingStepCompletionSessionId != sessionId) return@withLock current
        val updated = current.copy(
            pendingStepCompletionSessionId = null,
            pendingStepCompletionStepNumber = null,
        )
        persist(_plans.value + (taskId to updated))
        updated
    }

    suspend fun commitPreparedCompletion(taskId: String, sessionId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        val current = _plans.value[taskId] ?: return@withLock null
        if (current.pendingStepCompletionSessionId != sessionId) return@withLock current
        val stepNumber = current.pendingStepCompletionStepNumber
        val updated = (stepNumber?.let(current::completeStep) ?: current).copy(
            pendingStepCompletionSessionId = null,
            pendingStepCompletionStepNumber = null,
        )
        persist(_plans.value + (taskId to updated))
        updated
    }

    suspend fun recoverPreparedCompletions(completedSessionIds: Set<String>): List<FocusPlan> = mutex.withLock {
        ensureLoaded()
        val recovered = _plans.value.mapValues { (_, plan) ->
            val pendingSessionId = plan.pendingStepCompletionSessionId
            if (pendingSessionId != null && pendingSessionId in completedSessionIds) {
                val stepNumber = plan.pendingStepCompletionStepNumber
                (stepNumber?.let(plan::completeStep) ?: plan).copy(
                    pendingStepCompletionSessionId = null,
                    pendingStepCompletionStepNumber = null,
                )
            } else {
                plan
            }
        }
        if (recovered != _plans.value) persist(recovered)
        recovered.values.toList()
    }

    suspend fun acknowledgeTaskCompletion(taskId: String): FocusPlan? = mutex.withLock {
        ensureLoaded()
        val current = _plans.value[taskId] ?: return@withLock null
        if (!current.taskCompletionPending) return@withLock current
        val updated = current.copy(taskCompletionPending = false)
        persist(_plans.value + (taskId to updated))
        updated
    }

    suspend fun syncPendingTaskCompletions(
        completeTask: suspend (taskId: String) -> Boolean,
    ): List<String> {
        val (expectedStorageKey, pendingTaskIds) = mutex.withLock {
            ensureLoaded()
            checkNotNull(loadedKey) to _plans.value.values
                .filter { it.taskCompletionPending }
                .map { it.taskId }
        }
        val completedTaskIds = mutableListOf<String>()
        pendingTaskIds.forEach { taskId ->
            if (runCatching { completeTask(taskId) }.getOrDefault(false)) {
                val acknowledged = mutex.withLock {
                    if (loadedKey != expectedStorageKey || storageKey() != expectedStorageKey) {
                        return@withLock false
                    }
                    val current = _plans.value[taskId] ?: return@withLock false
                    if (!current.taskCompletionPending) return@withLock true
                    persist(_plans.value + (taskId to current.copy(taskCompletionPending = false)))
                    true
                }
                if (acknowledged) completedTaskIds += taskId
            }
        }
        return completedTaskIds
    }

    private suspend fun ensureLoaded() {
        val key = storageKey()
        if (loadedKey == key) return
        val restored = storage.readRaw(key)
            ?.let { raw -> runCatching { adapter.fromJson(raw).orEmpty() }.getOrDefault(emptyList()) }
            .orEmpty()
        _plans.value = restored.associateBy(FocusPlan::taskId)
        loadedKey = key
    }

    private suspend fun persist(plans: Map<String, FocusPlan>) {
        storage.saveRaw(checkNotNull(loadedKey), adapter.toJson(plans.values.sortedBy { it.taskId }))
        _plans.value = plans
    }

    private fun storageKey(): String = KEY_PREFIX + accountKey().trim().ifBlank { "anonymous" }.take(80)
}

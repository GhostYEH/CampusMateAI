package com.example.campusai

import com.example.campusai.data.local.InMemoryKeyValueStorage
import com.example.campusai.data.local.KeyValueStorage
import com.example.campusai.data.model.FocusPlan
import com.example.campusai.data.model.FocusPlanStep
import com.example.campusai.data.model.FocusPlanStepStatus
import com.example.campusai.data.repository.FocusPlanRepository
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.Flow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusPlanRepositoryTest {
    @Test
    fun completingCurrentStepAdvancesToTheNextStep() {
        val plan = samplePlan()

        assertEquals("阅读任务说明", plan.currentStep?.title)
        val afterFirst = plan.completeCurrentStep()
        assertEquals("完成第一组练习", afterFirst.currentStep?.title)
        assertEquals(FocusPlanStepStatus.COMPLETED, afterFirst.steps.first().status)
        assertFalse(afterFirst.isComplete)

        val completed = afterFirst.completeCurrentStep()
        assertTrue(completed.isComplete)
        assertEquals(null, completed.currentStep)
    }

    @Test
    fun stepProgressSurvivesRepositoryRecreation() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val firstRepository = FocusPlanRepository(storage)
        firstRepository.savePlan(samplePlan())
        firstRepository.completeCurrentStep("task-1")

        val restored = FocusPlanRepository(storage).getPlan("task-1")

        assertEquals(FocusPlanStepStatus.COMPLETED, restored?.steps?.first()?.status)
        assertEquals("完成第一组练习", restored?.currentStep?.title)
    }

    @Test
    fun finalStepStaysPendingForTaskSyncUntilAcknowledged() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan().completeCurrentStep())

        val completed = repository.completeCurrentStep("task-1")

        assertTrue(completed?.isComplete == true)
        assertTrue(completed?.taskCompletionPending == true)
        repository.acknowledgeTaskCompletion("task-1")
        val restored = FocusPlanRepository(storage).getPlan("task-1")
        assertFalse(restored?.taskCompletionPending == true)
    }

    @Test
    fun failedTaskSyncRemainsPendingAndSuccessfulRetryAcknowledgesIt() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan().completeCurrentStep().completeCurrentStep())

        repository.syncPendingTaskCompletions { false }
        assertTrue(repository.getPlan("task-1")?.taskCompletionPending == true)

        repository.syncPendingTaskCompletions { true }
        assertFalse(repository.getPlan("task-1")?.taskCompletionPending == true)
    }

    @Test
    fun accountSwitchDuringTaskSyncNeverAcknowledgesAnotherAccountsPlan() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        var account = "account-a"
        val repository = FocusPlanRepository(storage, accountKey = { account })
        repository.savePlan(samplePlan().completeCurrentStep().completeCurrentStep())

        repository.syncPendingTaskCompletions {
            account = "account-b"
            true
        }
        repository.load()
        assertTrue(repository.plans.value.isEmpty())

        account = "account-a"
        repository.load()
        assertTrue(repository.getPlan("task-1")?.taskCompletionPending == true)
    }

    @Test
    fun explicitLoadRestoresTheCurrentAccountAndSwitchesAccounts() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        var account = "account-a"
        val repository = FocusPlanRepository(storage, accountKey = { account })
        repository.savePlan(samplePlan().copy(taskTitle = "账号 A 的任务"))

        account = "account-b"
        repository.load()
        assertTrue(repository.plans.value.isEmpty())
        repository.savePlan(samplePlan().copy(taskTitle = "账号 B 的任务"))

        account = "account-a"
        repository.load()
        assertEquals("账号 A 的任务", repository.plans.value["task-1"]?.taskTitle)
    }

    @Test
    fun preparedCompletionIsRecoveredExactlyOnceAfterRemoteSessionDisappears() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan())
        repository.prepareStepCompletion("task-1", "session-1")

        repository.recoverPreparedCompletions(completedSessionIds = emptySet())
        assertEquals("阅读任务说明", repository.getPlan("task-1")?.currentStep?.title)

        repository.recoverPreparedCompletions(completedSessionIds = setOf("session-1"))
        assertEquals("完成第一组练习", repository.getPlan("task-1")?.currentStep?.title)
        assertEquals(null, repository.getPlan("task-1")?.pendingStepCompletionSessionId)

        repository.recoverPreparedCompletions(completedSessionIds = setOf("session-1"))
        assertEquals("完成第一组练习", repository.getPlan("task-1")?.currentStep?.title)
    }

    @Test
    fun endingWithoutStepCompletionCancelsAnEarlierPreparedIntent() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan())
        repository.prepareStepCompletion("task-1", "session-1")

        repository.discardPreparedCompletion("task-1", "session-1")
        repository.recoverPreparedCompletions(completedSessionIds = setOf("session-1"))

        assertEquals("阅读任务说明", repository.getPlan("task-1")?.currentStep?.title)
        assertEquals(null, repository.getPlan("task-1")?.pendingStepCompletionSessionId)
    }

    @Test
    fun preparedIntentNeverCompletesASecondStepWhenFirstWasAlreadyAdvanced() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan())
        repository.prepareStepCompletion("task-1", "session-1")
        repository.completeCurrentStep("task-1")

        repository.recoverPreparedCompletions(completedSessionIds = setOf("session-1"))

        val restored = repository.getPlan("task-1")
        assertEquals("完成第一组练习", restored?.currentStep?.title)
        assertEquals(null, restored?.pendingStepCompletionSessionId)
        assertEquals(null, restored?.pendingStepCompletionStepNumber)
    }

    @Test
    fun failedPersistenceDoesNotPublishAdvancedInMemoryState() = runBlocking {
        val storage = FailingWriteStorage()
        val repository = FocusPlanRepository(storage)
        repository.savePlan(samplePlan())
        storage.failWrites = true

        runCatching { repository.completeCurrentStep("task-1") }

        assertEquals("阅读任务说明", repository.plans.value["task-1"]?.currentStep?.title)
    }

    private fun samplePlan() = FocusPlan(
        taskId = "task-1",
        taskTitle = "复习数据结构",
        goal = "复习数据结构",
        steps = listOf(
            FocusPlanStep(1, "阅读任务说明", "明确范围", 10, "能说出本次目标"),
            FocusPlanStep(2, "完成第一组练习", "完成练习题", 25, "练习题已完成", dependencies = listOf(1)),
        ),
    )

    private class FailingWriteStorage : KeyValueStorage {
        private val delegate = InMemoryKeyValueStorage()
        var failWrites = false

        override fun observeRaw(key: String): Flow<String?> = delegate.observeRaw(key)

        override suspend fun readRaw(key: String): String? = delegate.readRaw(key)

        override suspend fun saveRaw(key: String, value: String) {
            if (failWrites) error("write failed")
            delegate.saveRaw(key, value)
        }
    }
}

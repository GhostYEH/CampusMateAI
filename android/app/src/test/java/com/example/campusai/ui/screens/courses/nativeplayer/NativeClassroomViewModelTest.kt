package com.example.campusai.ui.screens.courses.nativeplayer

import android.app.Application
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalIo
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalRestore
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalWriteGate
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewards
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsCodec
import com.example.campusai.data.classroom.nativeplayer.ClassroomSessionFlusher
import com.example.campusai.data.classroom.nativeplayer.ClassroomStateWrite
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomCache
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomSource
import com.example.campusai.data.classroom.nativeplayer.rewards
import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.mockito.kotlin.any
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import java.io.IOException

/**
 * ViewModel 级回归：同一会话状态同时控制首次打开、翻页与退出的位置/奖励写入。
 * 本地 IO 替身可以真实挂起恢复回读，用于验证「写完但未确认」期间其它打开只能等待或只读。
 */
@RunWith(RobolectricTestRunner::class)
class NativeClassroomViewModelTest {
    private lateinit var application: Application
    private lateinit var repository: AppRepository
    private lateinit var viewModel: NativeClassroomViewModel
    private val localIo = FakeClassroomLocalIo()
    private val scope = "svc_test_account"

    private val positionWrites get() = localIo.positionWrites
    private val rewardWrites get() = localIo.rewardWrites
    private var storedPosition: String?
        get() = localIo.storedPosition
        set(value) { localIo.storedPosition = value }
    private var storedRewards: String?
        get() = localIo.storedRewards
        set(value) { localIo.storedRewards = value }
    private var failWrites: Boolean
        get() = localIo.failWrites
        set(value) { localIo.failWrites = value }

    private val ref = NativeClassroomRef(
        courseId = "course",
        workspaceId = "workspace",
        stageId = "stage",
        title = "课堂",
        sessionId = "session",
        source = NativeClassroomSource.COURSE_CLASSIC,
    )

    private val positionKey get() = "local:position"
    private val rewardsKey get() = "local:rewards"

    @Before
    fun setUp() {
        runBlocking {
            ClassroomLocalWriteGate.reset()
            localIo.reset()
            application = ApplicationProvider.getApplicationContext()
            writeClassicCache()
            repository = mock()
            whenever(repository.classroomAccountScope()).thenReturn(scope)
            whenever(repository.classroomLocalKey(any(), any())).thenReturn("local")
            doReturn(Result.failure<ClassroomPlaybackDto>(IllegalStateException("offline")))
                .whenever(repository).classroomPlayback(any(), any())
        }
    }

    @After
    fun tearDown() {
        if (::viewModel.isInitialized) viewModel.endSession()
        ClassroomLocalWriteGate.reset()
        localIo.reset()
    }

    @Test
    fun previousSuccessRestoresPositionAndLedgerThenKeepsSaving() = runBlocking {
        val previousPosition = "scene-1"
        val previousRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 12, visited = setOf("scene-1")),
        )
        val nextRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 24, visited = setOf("scene-2")),
        )
        storedPosition = previousPosition
        storedRewards = previousRewards
        val previous = launchPreviousWrites(
            targetPosition = "scene-2",
            targetRewards = nextRewards,
        )
        delay(40)

        viewModel = newViewModel()
        viewModel.startSession()
        awaitUntil { viewModel.uiState.value.plan != null }
        previous.join()
        assertEquals("延迟写入应真正更新位置", "scene-2", storedPosition)
        assertEquals(
            "延迟写入应真正更新账本",
            24,
            ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp,
        )
        awaitUntil { positionWrites.isNotEmpty() }

        assertEquals("scene-2", viewModel.uiState.value.currentSceneId)
        assertEquals(24, viewModel.uiState.value.rewards.xp)
        assertTrue(positionWrites.contains("scene-2"))

        val pageWriteBaseline = positionWrites.size
        val pageRewardBaseline = rewardWrites.size
        viewModel.goTo(0)
        awaitUntil {
            positionWrites.size > pageWriteBaseline && positionWrites.last() == "scene-1"
        }
        awaitUntil { rewardWrites.size > pageRewardBaseline }
        assertEquals("scene-1", positionWrites.last())

        val pageWrites = positionWrites.size
        val pageRewardWrites = rewardWrites.size
        viewModel.endSession()
        awaitUntil { positionWrites.size > pageWrites && rewardWrites.size > pageRewardWrites }
        assertEquals("scene-1", positionWrites.last())
        assertTrue(rewardWrites.isNotEmpty())
    }

    @Test
    fun previousFailureKeepsReliableRecordsAndBlocksFirstOpenPageAndExitWrites() = runBlocking {
        val previousPosition = "scene-1"
        val previousRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 12, visited = setOf("scene-1")),
        )
        val nextRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 24, visited = setOf("scene-2")),
        )
        storedPosition = previousPosition
        storedRewards = previousRewards
        failWrites = true
        val previous = launchPreviousWrites(
            targetPosition = "scene-2",
            targetRewards = nextRewards,
            failPosition = true,
        )
        delay(40)

        viewModel = newViewModel()
        viewModel.startSession()
        awaitUntil { viewModel.uiState.value.plan != null }
        previous.join()

        assertEquals(previousPosition, viewModel.uiState.value.currentSceneId)
        assertEquals(24, viewModel.uiState.value.rewards.xp)
        assertTrue(viewModel.uiState.value.notice.orEmpty().contains("保存失败"))
        assertEquals(previousPosition, storedPosition)
        assertEquals(24, ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp)

        positionWrites.clear()
        rewardWrites.clear()
        viewModel.goTo(0)
        viewModel.endSession()
        delay(1_000)
        assertTrue(positionWrites.isEmpty())
        assertTrue(rewardWrites.isEmpty())
    }

    @Test
    fun failedWriteRecoversWhenStorageReturnsOnNextOpen() = runBlocking {
        storedPosition = "scene-0"
        storedRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 12, visited = setOf("scene-0")),
        )
        failWrites = true

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitUntil { first.uiState.value.plan != null }
        awaitUntil { positionWrites.isNotEmpty() && rewardWrites.isNotEmpty() }
        ClassroomLocalWriteGate.awaitIdle(positionKey)
        ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        delay(100)

        assertEquals("失败写入不能改位置", "scene-0", storedPosition)
        assertEquals(
            "失败写入不能改账本",
            12,
            ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp,
        )
        val failedPositions = positionWrites.size
        val failedRewards = rewardWrites.size

        first.goTo(1)
        first.endSession()
        delay(500)
        assertEquals("只读后翻页不能重试位置", failedPositions, positionWrites.size)
        assertEquals("只读后退场不能重试奖励", failedRewards, rewardWrites.size)

        failWrites = false
        positionWrites.clear()
        rewardWrites.clear()

        val second = newViewModel()
        viewModel = second
        second.startSession()
        awaitUntil { second.uiState.value.plan != null }
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 24
        }
        assertEquals("恢复后应重新开放位置保存", "scene-1", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        second.goTo(1)
        awaitUntil {
            storedPosition == "scene-2" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(36, second.uiState.value.rewards.xp)
    }

    @Test
    fun waitTimeoutStaysReadableButBlocksFirstOpenPageAndExitWrites() = runBlocking {
        ClassroomLocalWriteGate.beginPending(positionKey)
        ClassroomLocalWriteGate.beginPending(rewardsKey)

        viewModel = newViewModel()
        viewModel.startSession()
        awaitUntil(timeoutMs = 10_000L) { viewModel.uiState.value.plan != null }

        assertNotNull(viewModel.uiState.value.currentScenePlan)
        assertTrue(viewModel.uiState.value.notice.orEmpty().contains("尚未确认"))
        assertTrue(positionWrites.isEmpty())
        assertTrue(rewardWrites.isEmpty())

        viewModel.goTo(1)
        assertEquals(1, viewModel.uiState.value.index)
        assertEquals("scene-2", viewModel.uiState.value.currentSceneId)
        assertTrue(positionWrites.isEmpty())
        assertTrue(rewardWrites.isEmpty())

        viewModel.endSession()
        delay(1_000)
        assertTrue(positionWrites.isEmpty())
        assertTrue(rewardWrites.isEmpty())
    }

    @Test
    fun recoveryTimeoutStillLoadsWithBoundedLocalRead() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        // 恢复回读挂起后，普通加载也不能再一次无界等待同一份存储。
        localIo.alwaysHangPositionReads = true
        val first = newViewModel()
        viewModel = first
        val startedAt = System.currentTimeMillis()
        first.startSession()
        awaitUntil(timeoutMs = 6_000L) { first.uiState.value.plan != null }
        val elapsed = System.currentTimeMillis() - startedAt
        assertTrue("加载应在恢复预算和本地读取上限后降级完成", elapsed < 5_000L)
        assertNotNull("仍应加载可用课件", first.uiState.value.currentScenePlan)
        assertTrue("恢复失败时保持只读提示", first.uiState.value.notice.orEmpty().contains("保存失败"))
        withTimeout(1_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }
        assertTrue(ClassroomLocalWriteGate.needsRecovery(positionKey))
        first.endSession()
    }

    @Test
    fun recoveryReadBackKeepsSecondOpenPendingUntilConfirmed() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        val positionGate = CompletableDeferred<Unit>()
        val rewardsGate = CompletableDeferred<Unit>()
        localIo.readPositionGate = positionGate
        localIo.readRewardsGate = rewardsGate
        val readStarted = CompletableDeferred<Unit>().also { localIo.readStarted = it }

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitStarted(readStarted)

        val positionCount = positionWrites.size
        val rewardCount = rewardWrites.size
        val second = newViewModel()
        viewModel = second
        second.startSession()
        delay(80)
        assertTrue("第二次打开应等待首次恢复的回读确认", second.uiState.value.plan == null)
        assertEquals("等待期间不能领取位置写入", positionCount, positionWrites.size)
        assertEquals("等待期间不能领取奖励写入", rewardCount, rewardWrites.size)

        positionGate.complete(Unit)
        rewardsGate.complete(Unit)
        awaitUntil { first.uiState.value.plan != null && second.uiState.value.plan != null }
        assertEquals("scene-2", first.uiState.value.currentSceneId)
        assertEquals(24, first.uiState.value.rewards.xp)
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        first.endSession()
        withTimeout(1_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }

        second.goTo(0)
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        assertEquals("scene-1", second.uiState.value.currentSceneId)
        assertEquals(36, second.uiState.value.rewards.xp)
        second.endSession()
    }

    @Test
    fun recoveryReadBackFailureKeepsSnapshotAndNextOpenRechecks() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        localIo.failReads = true

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitUntil { first.uiState.value.plan != null }
        withTimeout(2_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }
        assertTrue("回读失败应保持只读提示", first.uiState.value.notice.orEmpty().contains("保存失败"))

        val positionCount = positionWrites.size
        val rewardCount = rewardWrites.size
        first.goTo(1)
        assertEquals(1, first.uiState.value.index)
        first.endSession()
        delay(500)
        assertEquals("只读后翻页不能写位置", positionCount, positionWrites.size)
        assertEquals("只读后退出不能写奖励", rewardCount, rewardWrites.size)
        assertTrue(ClassroomLocalWriteGate.needsRecovery(positionKey))
        assertNotNull("回读失败应保留仍有效的快照", ClassroomLocalWriteGate.latestSnapshot(positionKey))
        assertEquals(
            ClassroomLocalRestore.FAILED,
            ClassroomLocalWriteGate.restoreState(positionKey, rewardsKey, idle = true),
        )

        localIo.failReads = false
        val second = newViewModel()
        viewModel = second
        second.startSession()
        awaitUntil { second.uiState.value.plan != null }
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        second.goTo(0)
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        second.endSession()
    }

    @Test
    fun recoveryReadBackMismatchKeepsSnapshotAndNextOpenRechecks() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        localIo.queuedPositionReads += "scene-other"

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitUntil { first.uiState.value.plan != null }
        withTimeout(2_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }
        assertTrue("回读值不一致应保持只读提示", first.uiState.value.notice.orEmpty().contains("保存失败"))
        assertEquals("写入本身仍可留在磁盘上", "scene-2", storedPosition)

        val positionCount = positionWrites.size
        val rewardCount = rewardWrites.size
        first.goTo(0)
        first.endSession()
        delay(500)
        assertEquals(positionCount, positionWrites.size)
        assertEquals(rewardCount, rewardWrites.size)
        assertTrue(ClassroomLocalWriteGate.needsRecovery(positionKey))
        assertNotNull(ClassroomLocalWriteGate.latestSnapshot(positionKey))

        val second = newViewModel()
        viewModel = second
        second.startSession()
        awaitUntil { second.uiState.value.plan != null }
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        second.goTo(0)
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        second.endSession()
    }

    @Test
    fun recoveryReadBackTimeoutKeepsSnapshotAndReleasesWaiters() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        val positionGate = CompletableDeferred<Unit>()
        localIo.readPositionGate = positionGate
        val readStarted = CompletableDeferred<Unit>().also { localIo.readStarted = it }

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitStarted(readStarted)
        awaitUntil(timeoutMs = 4_000L) { first.uiState.value.plan != null }
        assertTrue("回读超时应保持只读提示", first.uiState.value.notice.orEmpty().contains("保存失败"))
        withTimeout(1_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }
        assertTrue("超时后仍保留快照供下次恢复", ClassroomLocalWriteGate.needsRecovery(positionKey))
        assertEquals(
            ClassroomLocalRestore.FAILED,
            ClassroomLocalWriteGate.restoreState(positionKey, rewardsKey, idle = true),
        )

        val positionCount = positionWrites.size
        val rewardCount = rewardWrites.size
        first.goTo(1)
        first.endSession()
        delay(500)
        assertEquals(positionCount, positionWrites.size)
        assertEquals(rewardCount, rewardWrites.size)

        val second = newViewModel()
        viewModel = second
        second.startSession()
        awaitUntil { second.uiState.value.plan != null }
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        second.goTo(0)
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        second.endSession()
    }

    @Test
    fun cancelledRecoveryKeepsSnapshotAndNextOpenStillChecks() = runBlocking {
        prepareFailedPreviousWrites(
            storedScene = "scene-1",
            storedXp = 12,
            storedVisited = setOf("scene-1"),
            targetScene = "scene-2",
            targetXp = 24,
            targetVisited = setOf("scene-2"),
        )
        val positionGate = CompletableDeferred<Unit>()
        localIo.readPositionGate = positionGate
        val readStarted = CompletableDeferred<Unit>().also { localIo.readStarted = it }

        val first = newViewModel()
        viewModel = first
        first.startSession()
        awaitStarted(readStarted)
        first.endSession()
        withTimeout(2_000L) {
            ClassroomLocalWriteGate.awaitIdle(positionKey)
            ClassroomLocalWriteGate.awaitIdle(rewardsKey)
        }
        assertTrue("取消后仍保留快照", ClassroomLocalWriteGate.needsRecovery(positionKey))
        assertNotNull(ClassroomLocalWriteGate.latestSnapshot(positionKey))
        assertEquals(
            ClassroomLocalRestore.FAILED,
            ClassroomLocalWriteGate.restoreState(positionKey, rewardsKey, idle = true),
        )

        val recoveryWritesBefore = positionWrites.size
        val second = newViewModel()
        viewModel = second
        second.startSession()
        awaitUntil { second.uiState.value.plan != null }
        assertTrue(
            "新会话必须重新核对/恢复，旧结果不能让它跳过校验",
            positionWrites.size > recoveryWritesBefore,
        )
        assertEquals("scene-2", second.uiState.value.currentSceneId)
        assertEquals(24, second.uiState.value.rewards.xp)

        second.goTo(0)
        awaitUntil {
            storedPosition == "scene-1" &&
                ClassroomRewardsCodec.decodeResult(storedRewards.orEmpty()).rewards?.xp == 36
        }
        second.endSession()
    }

    private fun newViewModel() = NativeClassroomViewModel(application, repository, ref, localIo = localIo)

    private suspend fun prepareFailedPreviousWrites(
        storedScene: String,
        storedXp: Int,
        storedVisited: Set<String>,
        targetScene: String,
        targetXp: Int,
        targetVisited: Set<String>,
    ) {
        storedPosition = storedScene
        storedRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = storedXp, visited = storedVisited),
        )
        launchPreviousWrites(
            targetPosition = targetScene,
            targetRewards = ClassroomRewardsCodec.encode(
                ClassroomRewards(xp = targetXp, visited = targetVisited),
            ),
            failPosition = true,
            failRewards = true,
        ).join()
        assertTrue("位置快照应保留以待恢复", ClassroomLocalWriteGate.needsRecovery(positionKey))
        assertTrue("奖励快照应保留以待恢复", ClassroomLocalWriteGate.needsRecovery(rewardsKey))
        assertTrue(
            "上一轮写入结束后不应留下待写标记",
            ClassroomLocalWriteGate.isIdle(positionKey, rewardsKey),
        )
        assertEquals(
            "上一轮失败应让下次打开进入恢复路径",
            ClassroomLocalRestore.FAILED,
            ClassroomLocalWriteGate.restoreState(positionKey, rewardsKey, idle = true),
        )
    }

    private suspend fun awaitStarted(signal: CompletableDeferred<Unit>, timeoutMs: Long = 3_000L) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (!signal.isCompleted && System.currentTimeMillis() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            delay(25)
        }
        assertTrue("等待恢复回读启动超时", signal.isCompleted)
    }

    private suspend fun awaitUntil(timeoutMs: Long = 6_000L, predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (!predicate() && System.currentTimeMillis() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            delay(25)
        }
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue("等待条件超时", predicate())
    }

    /** 上一轮会话的两笔写入用可控延迟完成；延迟结束后才真正更新测试存储。 */
    private fun launchPreviousWrites(
        targetPosition: String,
        targetRewards: String,
        failPosition: Boolean = false,
        failRewards: Boolean = false,
        delayMs: Long = 200,
    ): Job =
        CoroutineScope(Dispatchers.IO).launch(start = CoroutineStart.UNDISPATCHED) {
            val positionGrant = ClassroomLocalWriteGate.grant(positionKey).also {
                ClassroomLocalWriteGate.rememberSnapshot(positionKey, it, targetPosition)
            }
            val rewardsGrant = ClassroomLocalWriteGate.grant(rewardsKey).also {
                ClassroomLocalWriteGate.rememberSnapshot(rewardsKey, it, targetRewards)
            }
            val writes = listOf(
                ClassroomStateWrite(
                    key = positionKey,
                    label = "position",
                    grant = positionGrant,
                    save = {
                        delay(delayMs)
                        positionWrites += targetPosition
                        if (failPosition) throw IOException("previous position write failed")
                        storedPosition = targetPosition
                    },
                ),
                ClassroomStateWrite(
                    key = rewardsKey,
                    label = "rewards",
                    grant = rewardsGrant,
                    save = {
                        delay(delayMs)
                        rewardWrites += targetRewards
                        if (failRewards) throw IOException("previous rewards write failed")
                        storedRewards = targetRewards
                    },
                ),
            )
            ClassroomSessionFlusher(budgetMs = 2_000L, itemBudgetMs = 1_000L).run(writes)
        }

    private fun writeClassicCache() {
        NativeClassroomCache(application, scope, ref).writeClassicPlayback(
            ClassroomPlaybackDto(
                contractVersion = "v1",
                courseId = "course",
                sessionId = "session",
                classroomId = "classroom",
                contentVersion = "1",
                title = "课堂",
                scenes = listOf(
                    playableScene("scene-1", "第一页", 0),
                    playableScene("scene-2", "第二页", 1),
                ),
            ),
        )
    }

    private fun playableScene(id: String, title: String, order: Int) =
        ClassroomPlaybackSceneDto(
            id = id,
            type = "slide",
            title = title,
            order = order,
            content = mapOf("body" to title),
            render = mapOf("kind" to "native"),
        )

    private class FakeClassroomLocalIo : ClassroomLocalIo {
        var storedPosition: String? = null
        var storedRewards: String? = null
        val positionWrites = mutableListOf<String>()
        val rewardWrites = mutableListOf<String>()
        var failWrites = false
        var failReads = false
        var alwaysHangPositionReads = false
        var readPositionGate: CompletableDeferred<Unit>? = null
        var readRewardsGate: CompletableDeferred<Unit>? = null
        var readStarted: CompletableDeferred<Unit>? = null
        val queuedPositionReads = mutableListOf<String?>()
        val queuedRewardsReads = mutableListOf<String?>()

        fun reset() {
            storedPosition = null
            storedRewards = null
            positionWrites.clear()
            rewardWrites.clear()
            failWrites = false
            failReads = false
            alwaysHangPositionReads = false
            readPositionGate = null
            readRewardsGate = null
            readStarted = null
            queuedPositionReads.clear()
            queuedRewardsReads.clear()
        }

        override suspend fun readPosition(accountScope: String): String? {
            val gate = readPositionGate
            readPositionGate = null
            return readComponent(gate) {
                if (failReads) throw IOException("read failed")
                if (alwaysHangPositionReads) CompletableDeferred<Unit>().await()
                if (queuedPositionReads.isNotEmpty()) queuedPositionReads.removeAt(0) else storedPosition
            }
        }

        override suspend fun readRewardsRaw(accountScope: String): String? {
            val gate = readRewardsGate
            readRewardsGate = null
            return readComponent(gate) {
                if (failReads) throw IOException("read failed")
                if (queuedRewardsReads.isNotEmpty()) queuedRewardsReads.removeAt(0) else storedRewards
            }
        }

        override suspend fun savePosition(
            sceneId: String,
            accountScope: String,
            shouldWrite: () -> Boolean,
        ): Boolean {
            if (!shouldWrite()) return false
            positionWrites += sceneId
            if (failWrites) throw IOException("storage unavailable")
            storedPosition = sceneId
            return true
        }

        override suspend fun saveRewardsRaw(
            raw: String,
            accountScope: String,
            shouldWrite: () -> Boolean,
        ): Boolean {
            if (!shouldWrite()) return false
            rewardWrites += raw
            if (failWrites) throw IOException("storage unavailable")
            storedRewards = raw
            return true
        }

        private suspend fun <T> readComponent(
            gate: CompletableDeferred<Unit>?,
            read: suspend () -> T,
        ): T {
            readStarted?.complete(Unit)
            gate?.await()
            return read()
        }
    }
}

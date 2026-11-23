package com.example.campusai.ui.screens.courses.nativeplayer

import android.app.Application
import android.os.Looper
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.classroom.nativeplayer.ClassroomLocalWriteGate
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewards
import com.example.campusai.data.classroom.nativeplayer.ClassroomRewardsCodec
import com.example.campusai.data.classroom.nativeplayer.ClassroomSessionFlusher
import com.example.campusai.data.classroom.nativeplayer.ClassroomStateWrite
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomCache
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomSource
import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
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
import org.mockito.kotlin.doAnswer
import org.mockito.kotlin.doReturn
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever

/**
 * ViewModel 级回归：同一会话状态同时控制首次打开、翻页与退出的位置/奖励写入。
 * 用可控等待覆盖上一轮成功、失败、仍未完成三种读取屏障结果。
 */
@RunWith(RobolectricTestRunner::class)
class NativeClassroomViewModelTest {
    private lateinit var application: Application
    private lateinit var repository: AppRepository
    private lateinit var viewModel: NativeClassroomViewModel
    private val scope = "svc_test_account"
    private val positionWrites = mutableListOf<String>()
    private val rewardWrites = mutableListOf<String>()
    private var storedPosition: String? = null
    private var storedRewards: String? = null

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
    fun setUp() = runBlocking {
        ClassroomLocalWriteGate.reset()
        application = ApplicationProvider.getApplicationContext()
        writeClassicCache()
        repository = mock()
        whenever(repository.classroomAccountScope()).thenReturn(scope)
        whenever(repository.classroomLocalKey(any(), any())).thenReturn("local")
        doAnswer { storedPosition }.whenever(repository).classroomPosition(any())
        doAnswer { storedRewards }.whenever(repository).classroomRewardsRaw(any())
        doReturn(Result.failure<ClassroomPlaybackDto>(IllegalStateException("offline")))
            .whenever(repository).classroomPlayback(any(), any())
        doAnswer { invocation ->
            positionWrites += invocation.arguments[1] as String
            Unit
        }.whenever(repository).saveClassroomPosition(any(), any(), any(), any())
        doAnswer { invocation ->
            rewardWrites += invocation.arguments[1] as String
            Unit
        }.whenever(repository).saveClassroomRewardsRaw(any(), any(), any(), any())
    }

    @After
    fun tearDown() {
        if (::viewModel.isInitialized) viewModel.endSession()
        ClassroomLocalWriteGate.reset()
    }

    @Test
    fun previousSuccessRestoresPositionAndLedgerThenKeepsSaving() = runBlocking {
        storedPosition = "scene-2"
        storedRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 24, visited = setOf("scene-2")),
        )
        val previous = launchPreviousWrites(failPosition = false)
        delay(40)

        viewModel = NativeClassroomViewModel(application, repository, ref)
        viewModel.startSession()
        awaitUntil { viewModel.uiState.value.plan != null }
        previous.join()
        awaitUntil { positionWrites.isNotEmpty() }

        assertEquals("scene-2", viewModel.uiState.value.currentSceneId)
        assertEquals(24, viewModel.uiState.value.rewards.xp)
        assertTrue(positionWrites.contains("scene-2"))

        viewModel.goTo(0)
        awaitUntil { positionWrites.size >= 2 }
        awaitUntil { rewardWrites.isNotEmpty() }
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
        storedPosition = "scene-2"
        storedRewards = ClassroomRewardsCodec.encode(
            ClassroomRewards(xp = 24, visited = setOf("scene-2")),
        )
        val previous = launchPreviousWrites(failPosition = true)
        delay(40)

        viewModel = NativeClassroomViewModel(application, repository, ref)
        viewModel.startSession()
        awaitUntil { viewModel.uiState.value.plan != null }
        previous.join()

        assertEquals("scene-2", viewModel.uiState.value.currentSceneId)
        assertEquals(24, viewModel.uiState.value.rewards.xp)
        assertTrue(viewModel.uiState.value.notice.orEmpty().contains("保存失败"))

        viewModel.goTo(0)
        viewModel.endSession()
        delay(1_000)
        assertTrue(positionWrites.isEmpty())
        assertTrue(rewardWrites.isEmpty())
    }

    @Test
    fun waitTimeoutStaysReadableButBlocksFirstOpenPageAndExitWrites() = runBlocking {
        ClassroomLocalWriteGate.beginPending(positionKey)
        ClassroomLocalWriteGate.beginPending(rewardsKey)

        viewModel = NativeClassroomViewModel(application, repository, ref)
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

    private suspend fun awaitUntil(timeoutMs: Long = 6_000L, predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (!predicate() && System.currentTimeMillis() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            delay(25)
        }
        shadowOf(Looper.getMainLooper()).idle()
        assertTrue("等待条件超时", predicate())
    }

    /** 上一轮会话的两笔写入用可控延迟完成；失败项保留其它项结果。 */
    private fun launchPreviousWrites(failPosition: Boolean): Job =
        CoroutineScope(Dispatchers.IO).launch(start = kotlinx.coroutines.CoroutineStart.UNDISPATCHED) {
            val writes = listOf(
                ClassroomStateWrite(
                    key = positionKey,
                    label = "position",
                    grant = ClassroomLocalWriteGate.grant(positionKey),
                    save = {
                        delay(200)
                        if (failPosition) throw IllegalStateException("previous position write failed")
                    },
                ),
                ClassroomStateWrite(
                    key = rewardsKey,
                    label = "rewards",
                    grant = ClassroomLocalWriteGate.grant(rewardsKey),
                    save = { delay(200) },
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
}

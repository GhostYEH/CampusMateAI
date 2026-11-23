package com.example.campusai.ui.screens.classroom

import android.app.Application
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.test.core.app.ApplicationProvider
import com.example.campusai.data.remote.StudyRoom
import com.example.campusai.data.remote.StudyRoomApi
import com.example.campusai.data.remote.StudyRoomCreateRequest
import com.example.campusai.data.remote.StudyRoomIdentity
import com.example.campusai.data.remote.StudyRoomInvitations
import com.example.campusai.data.remote.StudyRoomInviteRequest
import com.example.campusai.data.remote.StudyRoomList
import com.example.campusai.data.remote.StudyRoomMessage
import com.example.campusai.data.remote.StudyRoomMessageRequest
import com.example.campusai.data.remote.StudyRoomMessages
import com.example.campusai.data.remote.StudyRoomStateRequest
import com.example.campusai.data.remote.StudyRoomTimerRequest
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
class StudyRoomViewModelTest {

    private val dispatcher = kotlinx.coroutines.test.StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun create(api: FakeStudyRoomApi): StudyRoomViewModel {
        val app = ApplicationProvider.getApplicationContext<Application>()
        return StudyRoomViewModel(app, api)
    }

    @Test
    fun `late room response after returning to list does not resurrect the room`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply {
            rooms["A"] = roomFixture("A")
        }
        val model = create(api)
        model.join("A")
        runCurrent()
        assertEquals("A", model.state.value.room?.id)

        api.roomGate = CompletableDeferred()
        model.foreground(true)
        runCurrent()

        model.returnToList()
        runCurrent()
        assertNull(model.state.value.room)

        api.roomGate?.complete(Unit)
        runCurrent()
        assertNull(model.state.value.room)
        assertTrue(model.state.value.messages.isEmpty())

        model.foreground(false)
        runCurrent()
    }

    @Test
    fun `stale page from room A cannot advance room B cursor`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply {
            rooms["A"] = roomFixture("A")
            rooms["B"] = roomFixture("B")
            messagesByRoom["A"] = listOf(message(101, "from-a"))
            messagesByRoom["B"] = listOf(message(5, "from-b"))
        }
        val model = create(api)
        model.join("A")
        runCurrent()

        api.messageGate = CompletableDeferred()
        api.gatedRoomId = "A"
        model.foreground(true)
        runCurrent()

        model.join("B")
        runCurrent()
        assertEquals("B", model.state.value.room?.id)
        assertTrue(model.state.value.messages.isEmpty())

        api.messageGate?.complete(Unit)
        runCurrent()
        // 迟到的 A 分页被代次拦下；B 仍从 0 开始拉取，id=5 不能被 101 游标跳过。
        advanceTimeBy(5_000)
        runCurrent()

        assertEquals("B", model.state.value.room?.id)
        assertEquals(listOf(5L), model.state.value.messages.map { it.id })

        model.foreground(false)
        runCurrent()
    }

    @Test
    fun `production android view model factory constructs study room`() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        val provider = ViewModelProvider(
            ViewModelStore(),
            ViewModelProvider.AndroidViewModelFactory.getInstance(app),
        )
        val model = provider[StudyRoomViewModel::class.java]
        assertEquals(0, model.state.value.sentVersion)
    }

    @Test
    fun `spaced draft sends normalized content and keeps raw editor text for clearing`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply { rooms["A"] = roomFixture("A") }
        val model = create(api)
        model.join("A")
        runCurrent()

        model.send("  一起加油  ")
        runCurrent()

        assertEquals("一起加油", api.sendRequests.single().content)
        assertEquals(1, model.state.value.sentVersion)
        assertEquals("  一起加油  ", model.state.value.sentDraft)
        assertNull(model.state.value.pendingMessage)
    }

    @Test
    fun `late send after editing still exposes the original editor text`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply { rooms["A"] = roomFixture("A") }
        val model = create(api)
        model.join("A")
        runCurrent()

        api.sendGate = CompletableDeferred()
        model.send("  原稿  ")
        runCurrent()

        // The user keeps typing while the POST is in flight.
        api.sendGate?.complete(Unit)
        runCurrent()

        assertEquals("原稿", api.sendRequests.single().content)
        assertEquals("  原稿  ", model.state.value.sentDraft)
        assertEquals(1, model.state.value.sentVersion)
        assertTrue(shouldClearSentDraft(model.state.value.sentDraft, "  原稿  "))
        assertFalse(shouldClearSentDraft(model.state.value.sentDraft, "  原稿  续写"))
    }

    @Test
    fun `retry reuses client id and content and stores only one message`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply { rooms["A"] = roomFixture("A") }
        val model = create(api)
        model.join("A")
        runCurrent()

        api.sendFailure = IOException("response lost")
        model.send("一起加油")
        runCurrent()

        val pending = model.state.value.pendingMessage
        assertEquals("一起加油", pending?.draft)
        val firstClientId = pending?.clientId
        assertEquals(0, model.state.value.sentVersion)

        api.sendFailure = null
        model.retryMessage()
        runCurrent()

        assertEquals(2, api.sendRequests.size)
        assertEquals(firstClientId, api.sendRequests[0].client_id)
        assertEquals(firstClientId, api.sendRequests[1].client_id)
        assertEquals("一起加油", api.sendRequests[1].content)
        assertEquals(1, api.sentByClient.size)
        assertNull(model.state.value.pendingMessage)
        assertEquals(1, model.state.value.sentVersion)
        assertEquals("一起加油", model.state.value.sentDraft)
        assertEquals(listOf(501L), model.state.value.messages.map { it.id })
    }

    @Test
    fun `post success is kept sent even when the follow-up pull fails`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply { rooms["A"] = roomFixture("A") }
        val model = create(api)
        model.join("A")
        runCurrent()

        api.failMessagePull = true
        model.send("先发出去")
        runCurrent()

        assertNull(model.state.value.pendingMessage)
        assertEquals(1, model.state.value.sentVersion)
        assertEquals("先发出去", model.state.value.sentDraft)
        assertTrue(model.state.value.messages.isEmpty())
    }

    @Test
    fun `explicit rejection clears the pending message but keeps the draft`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply {
            rooms["A"] = roomFixture("A")
            sendFailure = httpError(422)
        }
        val model = create(api)
        model.join("A")
        runCurrent()

        model.send("超长内容")
        runCurrent()

        assertNull(model.state.value.pendingMessage)
        assertEquals(0, model.state.value.sentVersion)
        assertTrue(model.state.value.notice?.contains("请检查输入内容") == true)
        assertEquals(1, api.sendRequests.size)
        assertNull(model.state.value.sentDraft)
    }

    @Test
    fun `polling pages through 100-message pages without dropping the cursor`() = runTest(dispatcher) {
        val api = FakeStudyRoomApi().apply {
            rooms["A"] = roomFixture("A")
            messagesByRoom["A"] = (1L..105L).map { message(it, "m$it") }
        }
        val model = create(api)
        model.join("A")
        runCurrent()

        model.foreground(true)
        runCurrent()
        advanceTimeBy(5_000)
        runCurrent()

        assertEquals(105, model.state.value.messages.size)
        assertEquals(105L, model.state.value.messages.last().id)
        assertEquals((1L..105L).toList(), model.state.value.messages.map { it.id })

        model.foreground(false)
        runCurrent()
    }

    private fun roomFixture(id: String) = StudyRoom(
        id = id,
        title = "自习室 $id",
        host_uid = "u1",
        members = emptyList(),
    )

    private fun message(id: Long, content: String) = StudyRoomMessage(
        id = id,
        uid = "u1",
        name = "我",
        content = content,
    )

    private fun httpError(code: Int) = HttpException(
        Response.error<Any>(code, "{}".toResponseBody("application/json".toMediaType())),
    )
}

private class FakeStudyRoomApi : StudyRoomApi {
    val rooms = mutableMapOf<String, StudyRoom>()
    val messagesByRoom = mutableMapOf<String, List<StudyRoomMessage>>()
    var roomGate: CompletableDeferred<Unit>? = null
    var messageGate: CompletableDeferred<Unit>? = null
    var gatedRoomId: String? = null
    var failMessagePull = false
    var sendFailure: Exception? = null
    var sendGate: CompletableDeferred<Unit>? = null
    val sendRequests = mutableListOf<StudyRoomMessageRequest>()
    val sentByClient = mutableMapOf<String, StudyRoomMessage>()
    private var nextMessageId = 501L

    override suspend fun identity() = StudyRoomIdentity(uid = "u1", name = "我")

    override suspend fun student(uid: String) = StudyRoomIdentity(uid = uid, name = uid)

    override suspend fun rooms() = StudyRoomList(rooms.values.map {
        com.example.campusai.data.remote.StudyRoomSummary(id = it.id, title = it.title, host_uid = it.host_uid)
    })

    override suspend fun invitations() = StudyRoomInvitations()

    override suspend fun create(body: StudyRoomCreateRequest): StudyRoom = error("unused")

    override suspend fun room(id: String): StudyRoom {
        roomGate?.await()
        return rooms[id] ?: error("missing room $id")
    }

    override suspend fun invite(id: String, body: StudyRoomInviteRequest) = Unit

    override suspend fun accept(id: String): StudyRoom = error("unused")

    override suspend fun decline(id: String) = Unit

    override suspend fun setState(id: String, body: StudyRoomStateRequest) = Unit

    override suspend fun heartbeat(id: String): Map<String, Any> = emptyMap()

    override suspend fun timer(id: String, body: StudyRoomTimerRequest): StudyRoom = error("unused")

    override suspend fun messages(id: String, after: Long): StudyRoomMessages {
        if (messageGate != null && id == gatedRoomId) messageGate?.await()
        if (failMessagePull) throw IOException("pull failed")
        return StudyRoomMessages(
            items = messagesByRoom[id].orEmpty().filter { it.id > after }.take(100),
        )
    }

    override suspend fun send(id: String, body: StudyRoomMessageRequest): Map<String, Any> {
        sendRequests += body
        sendGate?.await()
        sendFailure?.let { throw it }
        if (body.client_id !in sentByClient) {
            val message = StudyRoomMessage(
                id = nextMessageId++,
                uid = "u1",
                name = "我",
                content = body.content,
            )
            sentByClient[body.client_id] = message
            messagesByRoom[id] = messagesByRoom[id].orEmpty() + message
        }
        return emptyMap()
    }

    override suspend fun leave(id: String) = Unit
}

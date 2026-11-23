package com.example.campusai.data.classroom.nativeplayer

import android.net.Uri
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.TransferListener
import java.io.IOException
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class ClassroomMediaDataSourceTest {

    private class Events : TransferListener {
        var initializing = 0
        var started = 0
        var ended = 0
        var bytes = 0
        override fun onTransferInitializing(source: DataSource, dataSpec: DataSpec, isNetwork: Boolean) {
            initializing++
        }

        override fun onTransferStart(source: DataSource, dataSpec: DataSpec, isNetwork: Boolean) {
            started++
        }

        override fun onTransferEnd(source: DataSource, dataSpec: DataSpec, isNetwork: Boolean) {
            ended++
        }

        override fun onBytesTransferred(
            source: DataSource,
            dataSpec: DataSpec,
            isNetwork: Boolean,
            bytesTransferred: Int,
        ) {
            bytes += bytesTransferred
        }
    }

    private val apiBase = "https://api.example.com"
    private val mediaUri = "https://api.example.com/api/v1/courses/c1/interactive-classroom/s1/media/media/audio.mp3"

    private fun dataSource(handler: (Request) -> Response): DataSource {
        val client = OkHttpClient.Builder()
            .addInterceptor { chain ->
                handler(chain.request())
            }
            .build()
        return ClassroomMediaDataSourceFactory(
            client = client,
            ref = NativeClassroomRef(
                courseId = "c1",
                workspaceId = "",
                stageId = "",
                sessionId = "s1",
                source = NativeClassroomSource.COURSE_CLASSIC,
            ),
            apiBaseUrl = apiBase,
        ).createDataSource()
    }

    private fun response(request: Request, code: Int, body: String): Response =
        Response.Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(code)
            .message(if (code == 206) "Partial Content" else "OK")
            .body(body.toResponseBody(null))
            .build()

    private fun spec(position: Long = 0L, length: Long = -1L): DataSpec =
        DataSpec.Builder()
            .setUri(Uri.parse(mediaUri))
            .setPosition(position)
            .setLength(length)
            .build()

    @Test
    fun `server ignoring Range returns the requested slice and pairs transfer events`() {
        val source = dataSource { request -> response(request, 200, "0123456789") }
        val events = Events()
        source.addTransferListener(events)

        assertEquals(4L, source.open(spec(position = 3L, length = 4L)))
        val buffer = ByteArray(4)
        assertEquals(4, source.read(buffer, 0, 4))
        assertEquals("3456", String(buffer, Charsets.UTF_8))
        source.close()
        source.close()

        assertEquals(1, events.started)
        assertEquals(1, events.ended)
        assertEquals(4, events.bytes)
    }

    @Test
    fun `skip past the body fails before transfer start and leaves no end event`() {
        val source = dataSource { request -> response(request, 200, "short") }
        val events = Events()
        source.addTransferListener(events)

        assertTrue(
            runCatching { source.open(spec(position = 10L, length = 2L)) }.exceptionOrNull() is IOException,
        )
        source.close()
        source.close()
        assertEquals(0, events.started)
        assertEquals(0, events.ended)
    }

    @Test
    fun `successful open after a failed open still pairs events`() {
        var failFirst = true
        val source = dataSource { request ->
            if (failFirst) {
                failFirst = false
                response(request, 200, "short")
            } else {
                response(request, 206, "234567")
            }
        }
        val events = Events()
        source.addTransferListener(events)

        runCatching { source.open(spec(position = 10L)) }
        assertEquals(3L, source.open(spec(position = 2L, length = 3L)))
        val buffer = ByteArray(3)
        assertEquals(3, source.read(buffer, 0, 3))
        assertEquals("234", String(buffer, Charsets.UTF_8))
        source.close()

        assertEquals(1, events.started)
        assertEquals(1, events.ended)
    }

    @Test
    fun `416 fails without transfer events`() {
        val source = dataSource { request -> response(request, 416, "") }
        val events = Events()
        source.addTransferListener(events)

        assertTrue(runCatching { source.open(spec(position = 100L)) }.isFailure)
        source.close()
        assertEquals(0, events.started)
        assertEquals(0, events.ended)
    }

    @Test
    fun `redirect outside the trusted origin is rejected before transfer`() {
        val source = dataSource { request ->
            Response.Builder()
                .request(request)
                .protocol(Protocol.HTTP_1_1)
                .code(302)
                .message("Found")
                .header("Location", "https://evil.example.com/audio.mp3")
                .body("".toResponseBody(null))
                .build()
        }
        val events = Events()
        source.addTransferListener(events)

        assertTrue(runCatching { source.open(spec()) }.exceptionOrNull() is IOException)
        source.close()
        assertEquals(0, events.started)
        assertEquals(0, events.ended)
    }
}

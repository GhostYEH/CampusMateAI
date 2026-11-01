package com.example.campusai.data.audio

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

class WavSpeechRecorderTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test
    fun `automatic limit releases the device and retains exactly the allowed WAV frames`() {
        val requests = Collections.synchronizedList(mutableListOf<Int>())
        val capture = FakeCapture(bufferSize = 6418) { buffer, count ->
            requests.add(count)
            buffer.fill(0x23, 0, count)
            count
        }
        val recorder = recorder(capture)
        val finished = CountDownLatch(1)
        assertTrue(recorder.start { finished.countDown() })
        assertTrue(finished.await(2, TimeUnit.SECONDS))
        assertFalse(recorder.isRecording)
        assertEquals(1, capture.stopCount.get())
        assertEquals(1, capture.releaseCount.get())
        assertEquals(32000, requests.sum())
        assertTrue(requests.all { it % 2 == 0 })
        assertTrue(requests.last() < capture.bufferSize)

        val file = recorder.stop()
        assertNotNull(file)
        val wav = file!!.readBytes()
        assertEquals(32044, wav.size)
        assertEquals("RIFF", String(wav, 0, 4, Charsets.US_ASCII))
        assertEquals("WAVE", String(wav, 8, 4, Charsets.US_ASCII))
        assertEquals(16000, littleInt(wav, 24))
        assertEquals(32000, littleInt(wav, 40))
        assertArrayEquals(ByteArray(32000) { 0x23 }, wav.copyOfRange(44, wav.size))
        assertNull(recorder.stop())
    }

    @Test
    fun `manual stop unblocks a read before consuming its buffer and does not notify twice`() {
        val blocked = CountDownLatch(1)
        val unblocked = CountDownLatch(1)
        var reads = 0
        val capture = FakeCapture(onStop = { unblocked.countDown() }) { buffer, _ ->
            if (reads++ == 0) {
                buffer.fill(7, 0, 3200)
                3200
            } else {
                blocked.countDown()
                check(unblocked.await(2, TimeUnit.SECONDS))
                -3
            }
        }
        val notifications = AtomicInteger()
        val recorder = recorder(capture)
        assertTrue(recorder.start { notifications.incrementAndGet() })
        assertTrue(blocked.await(2, TimeUnit.SECONDS))
        val file = recorder.stop()
        assertNotNull(file)
        assertEquals(3244L, file!!.length())
        assertEquals(0, notifications.get())
        assertEquals(1, capture.stopCount.get())
        assertEquals(1, capture.releaseCount.get())
    }

    @Test
    fun `read failure ends capture and allows captured complete frames to be finalized`() {
        var reads = 0
        val capture = FakeCapture { buffer, _ ->
            if (reads++ == 0) {
                buffer.fill(5, 0, 3200)
                3200
            } else {
                throw IllegalStateException("device disconnected")
            }
        }
        val finished = CountDownLatch(1)
        val recorder = recorder(capture)
        assertTrue(recorder.start { finished.countDown() })
        assertTrue(finished.await(2, TimeUnit.SECONDS))
        assertFalse(recorder.isRecording)
        assertEquals(1, capture.releaseCount.get())
        assertEquals(3244L, recorder.stop()!!.length())
    }

    @Test
    fun `cancel discards capture and suppresses completion without resetting a live buffer`() {
        val blocked = CountDownLatch(1)
        val unblocked = CountDownLatch(1)
        val released = CountDownLatch(1)
        val capture = FakeCapture(
            onStop = { unblocked.countDown() },
            onRelease = { released.countDown() },
        ) { _, _ ->
            blocked.countDown()
            check(unblocked.await(2, TimeUnit.SECONDS))
            -3
        }
        val notifications = AtomicInteger()
        val recorder = recorder(capture)
        assertTrue(recorder.start { notifications.incrementAndGet() })
        assertTrue(blocked.await(2, TimeUnit.SECONDS))
        recorder.cancel()
        assertTrue(released.await(2, TimeUnit.SECONDS))
        assertFalse(recorder.isRecording)
        assertNull(recorder.stop())
        assertEquals(0, notifications.get())
        assertEquals(1, capture.stopCount.get())
        assertEquals(1, capture.releaseCount.get())
        assertTrue(temporary.root.listFiles().orEmpty().isEmpty())
    }

    @Test
    fun `cancel while stop is awaiting the final read discards the pending WAV`() {
        val blocked = CountDownLatch(1)
        val stopCalled = CountDownLatch(1)
        val allowReadToFinish = CountDownLatch(1)
        var reads = 0
        val capture = FakeCapture(onStop = { stopCalled.countDown() }) { buffer, _ ->
            if (reads++ == 0) {
                buffer.fill(3, 0, 3200)
                3200
            } else {
                blocked.countDown()
                check(allowReadToFinish.await(2, TimeUnit.SECONDS))
                -3
            }
        }
        val recorder = recorder(capture)
        assertTrue(recorder.start())
        assertTrue(blocked.await(2, TimeUnit.SECONDS))
        val output = AtomicReference<java.io.File?>()
        val stopping = Thread { output.set(recorder.stop()) }.also { it.start() }
        assertTrue(stopCalled.await(2, TimeUnit.SECONDS))
        recorder.cancel()
        allowReadToFinish.countDown()
        stopping.join(2000)
        assertFalse(stopping.isAlive)
        assertNull(output.get())
        assertEquals(1, capture.stopCount.get())
        assertEquals(1, capture.releaseCount.get())
        assertTrue(temporary.root.listFiles().orEmpty().isEmpty())
    }

    @Test
    fun `startup failure releases the device without reporting a completed recording`() {
        val capture = FakeCapture(onStart = { throw IllegalStateException("microphone unavailable") }) { _, _ -> -3 }
        val notifications = AtomicInteger()
        val recorder = recorder(capture)
        assertFalse(recorder.start { notifications.incrementAndGet() })
        assertFalse(recorder.isRecording)
        assertNull(recorder.stop())
        assertEquals(0, notifications.get())
        assertEquals(1, capture.releaseCount.get())
    }

    @Test
    fun `invalid PCM frames are not uploaded`() {
        val finished = CountDownLatch(1)
        val capture = FakeCapture { _, _ -> 1 }
        val recorder = recorder(capture)
        assertTrue(recorder.start { finished.countDown() })
        assertTrue(finished.await(2, TimeUnit.SECONDS))
        assertNull(recorder.stop())
    }

    private fun recorder(capture: SpeechAudioCapture) = WavSpeechRecorder(
        temporary.root, sampleRate = 16000, maxSeconds = 1, createCapture = { capture },
    )

    private fun littleInt(data: ByteArray, offset: Int): Int =
        ByteBuffer.wrap(data, offset, 4).order(ByteOrder.LITTLE_ENDIAN).int

    private class FakeCapture(
        override val bufferSize: Int = 6400,
        private val onStart: () -> Unit = {},
        private val onStop: () -> Unit = {},
        private val onRelease: () -> Unit = {},
        private val readBytes: (ByteArray, Int) -> Int,
    ) : SpeechAudioCapture {
        val stopCount = AtomicInteger()
        val releaseCount = AtomicInteger()
        override fun start() = onStart()
        override fun read(buffer: ByteArray, count: Int): Int = readBytes(buffer, count)
        override fun stop() { stopCount.incrementAndGet(); onStop() }
        override fun release() { releaseCount.incrementAndGet(); onRelease() }
    }
}

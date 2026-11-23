package com.example.campusai.data.remote

import org.junit.Assert.assertEquals
import org.junit.Test

class ApiClientLoggingTest {
    @Test
    fun basicHttpLogDropsQueryButKeepsPathAndTiming() {
        assertEquals(
            "--> GET https://api.example.com/study/rooms",
            redactBasicHttpLog("--> GET https://api.example.com/study/rooms?token=secret&uid=42"),
        )
        assertEquals(
            "<-- 200 OK https://api.example.com/study/rooms (123ms)",
            redactBasicHttpLog("<-- 200 OK https://api.example.com/study/rooms?token=secret&uid=42 (123ms)"),
        )
    }

    @Test
    fun basicHttpLogWithoutQueryIsUnchanged() {
        val message = "--> POST https://api.example.com/study/rooms"
        assertEquals(message, redactBasicHttpLog(message))
    }
}

package com.example.campusai.data.classroom

import org.junit.Assert.assertEquals
import org.junit.Test

class ClassroomConnectionTrackerTest {
    @Test
    fun `initial transport interruption and recovery never admit the room`() {
        val connection = ClassroomConnectionTracker()
        connection.begin()
        connection.transportChanged(false)
        connection.transportChanged(true)
        assertEquals(ClassroomCallPhase.CONNECTING, connection.phase)
        connection.roomJoined()
        assertEquals(ClassroomCallPhase.CONNECTED, connection.phase)
    }

    @Test
    fun `reconnection waits for room admission and reset forgets the old admission`() {
        val connection = ClassroomConnectionTracker()
        connection.begin()
        connection.roomJoined()
        connection.transportChanged(false)
        assertEquals(ClassroomCallPhase.RECONNECTING, connection.phase)
        connection.transportChanged(true)
        assertEquals(ClassroomCallPhase.RECONNECTING, connection.phase)
        connection.roomJoined()
        assertEquals(ClassroomCallPhase.CONNECTED, connection.phase)
        connection.reset()
        connection.begin()
        connection.transportChanged(false)
        assertEquals(ClassroomCallPhase.CONNECTING, connection.phase)
    }
}

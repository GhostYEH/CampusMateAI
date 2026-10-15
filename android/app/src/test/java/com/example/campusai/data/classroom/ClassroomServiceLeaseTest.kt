package com.example.campusai.data.classroom

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomServiceLeaseTest {
    @Test
    fun `old page cannot release the new page call or run a stale ready callback`() {
        val lease = ClassroomServiceLease()
        val oldPage = Any()
        val newPage = Any()
        var oldStops = 0
        var newStops = 0
        var oldReady = 0
        var newReady = 0
        val oldEpoch = lease.claim(oldPage, { oldStops++ }, { oldReady++ })
        val newEpoch = lease.claim(newPage, { newStops++ }, { newReady++ })

        assertEquals(1, oldStops)
        assertFalse(lease.release(oldPage))
        lease.stop(oldEpoch)
        lease.ready(oldEpoch)
        assertEquals(0, oldReady)
        assertEquals(0, newStops)
        assertTrue(lease.isCurrent(newEpoch))
        lease.ready(newEpoch)
        lease.ready(newEpoch)
        assertEquals(1, newReady)
        lease.stop(newEpoch)
        assertEquals(1, newStops)
        assertFalse(lease.hasOwner)
    }

    @Test
    fun `upgrading the same owner keeps the call and ignores the old service destroy`() {
        val lease = ClassroomServiceLease()
        val page = Any()
        var stops = 0
        val playback = lease.claim(page, { stops++ }, {})
        val microphone = lease.claim(page, { stops++ }, {})

        lease.stop(playback)
        assertEquals(0, stops)
        assertTrue(lease.isCurrent(microphone))
        assertTrue(lease.release(page))
        lease.stop(microphone)
        assertEquals(0, stops)
        assertFalse(lease.hasOwner)
    }

    @Test
    fun `stop callback may claim a new call without the old cleanup erasing it`() {
        val lease = ClassroomServiceLease()
        val next = Any()
        var nextEpoch = -1L
        val first = lease.claim(Any(), { nextEpoch = lease.claim(next, {}, {}) }, {})

        lease.stop(first)
        assertTrue(lease.isCurrent(nextEpoch))
        assertTrue(lease.release(next))
    }

    @Test
    fun `takeover detaches the old owner before its cleanup can stop the service`() {
        val lease = ClassroomServiceLease()
        val oldPage = Any()
        var oldCleanupMayStopService = true
        lease.claim(oldPage, { oldCleanupMayStopService = lease.release(oldPage) }, {})
        val nextEpoch = lease.claim(Any(), {}, {})

        assertFalse(oldCleanupMayStopService)
        assertTrue(lease.isCurrent(nextEpoch))
    }
}

package com.example.campusai.data.classroom

enum class ClassroomCallPhase { OFF, CONNECTING, CONNECTED, RECONNECTING, ERROR }

/** Transport recovery alone never proves that the server admitted us to the room. */
internal class ClassroomConnectionTracker {
    var phase: ClassroomCallPhase = ClassroomCallPhase.OFF
        private set
    private var admitted = false

    fun begin() {
        admitted = false
        phase = ClassroomCallPhase.CONNECTING
    }

    fun roomJoined() {
        admitted = true
        phase = ClassroomCallPhase.CONNECTED
    }

    fun transportChanged(connected: Boolean) {
        if (!connected && admitted) phase = ClassroomCallPhase.RECONNECTING
        // On recovery wait for the next room-success callback.
    }

    fun reset() {
        admitted = false
        phase = ClassroomCallPhase.OFF
    }
}

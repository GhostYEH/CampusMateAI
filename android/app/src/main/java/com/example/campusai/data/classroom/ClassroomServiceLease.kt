package com.example.campusai.data.classroom

/** Main-thread ownership of the one foreground service shared by classroom pages. */
internal class ClassroomServiceLease {
    private var owner: Any? = null
    private var onStop: (() -> Unit)? = null
    private var onReady: (() -> Unit)? = null
    private var generation = 0L
    val hasOwner: Boolean get() = owner != null

    fun claim(owner: Any, onStop: () -> Unit, onReady: () -> Unit): Long {
        // Stop the previous SDK engine before another page creates a new one.
        if (this.owner !== owner && hasOwner) {
            val previous = this.onStop
            clear()
            // Detach first so the old controller's cleanup cannot request a
            // stopService while we transfer the existing service to this call.
            previous?.invoke()
        }
        this.owner = owner
        this.onStop = onStop
        this.onReady = onReady
        return ++generation
    }

    fun isCurrent(expected: Long): Boolean = hasOwner && expected == generation

    fun ready(expected: Long) {
        if (!isCurrent(expected)) return
        val callback = onReady
        onReady = null
        callback?.invoke()
    }

    fun release(owner: Any): Boolean {
        if (this.owner !== owner) return false
        clear()
        return true
    }

    fun stop(expected: Long) {
        if (!isCurrent(expected)) return
        val callback = onStop
        clear() // Clear before notifying: the callback may release or start a new call.
        callback?.invoke()
    }

    private fun clear() {
        generation++
        owner = null
        onStop = null
        onReady = null
    }
}

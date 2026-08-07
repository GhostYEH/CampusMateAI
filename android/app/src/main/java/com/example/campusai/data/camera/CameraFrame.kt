package com.example.campusai.data.camera

import android.graphics.Bitmap

/**
 * A wrapper for a camera frame that allows reference counting
 * for asynchronous multi-analyzer distribution.
 */
class CameraFrame(
    val bitmap: Bitmap,
    val timestampMs: Long
) {
    private var refCount = 1

    @Synchronized
    fun retain() {
        refCount++
    }

    @Synchronized
    fun release() {
        refCount--
        if (refCount == 0 && !bitmap.isRecycled) {
            bitmap.recycle()
        }
    }
}

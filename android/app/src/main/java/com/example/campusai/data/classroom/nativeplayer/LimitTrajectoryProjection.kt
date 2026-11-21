package com.example.campusai.data.classroom.nativeplayer

import kotlin.math.cos
import kotlin.math.sin

/** A point on independently normalized x, f(x), and elapsed-time axes. */
internal data class LimitTrajectoryPoint(val x: Float, val y: Float, val time: Float)

internal class LimitTrajectoryProjection(angle: ClassroomLimitExperiment.ViewAngle) {
    data class Point(val x: Float, val y: Float)

    private val yaw = angle.yaw * (Math.PI / 180).toFloat()
    private val pitch = angle.pitch * (Math.PI / 180).toFloat()
    private val cosYaw = cos(yaw)
    private val sinYaw = sin(yaw)
    private val cosPitch = cos(pitch)
    private val sinPitch = sin(pitch)

    fun project(point: LimitTrajectoryPoint): Point {
        val x = (point.x - .5f) * 2f
        val y = (point.y - .5f) * 1.45f
        val z = (point.time - .5f) * 1.85f
        val horizontal = x * cosYaw - z * sinYaw
        val depth = x * sinYaw + z * cosYaw
        val vertical = y * cosPitch - depth * sinPitch
        val cameraDistance = 5f
        val scale = cameraDistance / (cameraDistance + y * sinPitch + depth * cosPitch)
        return Point(horizontal * scale, -vertical * scale)
    }
}

package com.example.campusai.data.classroom.nativeplayer

import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.sin

internal data class SpatialMesh(val vertices: List<SpatialVector>, val faces: List<IntArray>)

internal object ClassroomSpatialGeometry {
    val meshes: Map<SpatialShape, SpatialMesh> by lazy {
        val box = SpatialMesh(
            vertices = listOf(
                SpatialVector(-.5f, -.5f, -.5f), SpatialVector(.5f, -.5f, -.5f),
                SpatialVector(.5f, .5f, -.5f), SpatialVector(-.5f, .5f, -.5f),
                SpatialVector(-.5f, -.5f, .5f), SpatialVector(.5f, -.5f, .5f),
                SpatialVector(.5f, .5f, .5f), SpatialVector(-.5f, .5f, .5f),
            ),
            faces = listOf(
                intArrayOf(0, 3, 2, 1), intArrayOf(4, 5, 6, 7), intArrayOf(0, 4, 7, 3),
                intArrayOf(1, 2, 6, 5), intArrayOf(0, 1, 5, 4), intArrayOf(3, 7, 6, 2),
            ),
        )
        mapOf(
            SpatialShape.BOX to box,
            SpatialShape.PLANE to SpatialMesh(box.vertices.take(4).map { it.copy(z = 0f) }, listOf(intArrayOf(0, 1, 2, 3))),
            SpatialShape.SPHERE to revolve((0..10).map { index ->
                val angle = index * PI / 10
                (-.5f * cos(angle).toFloat()) to (.5f * sin(angle).toFloat())
            }),
            SpatialShape.CYLINDER to revolve(listOf(-.5f to 0f, -.5f to .5f, .5f to .5f, .5f to 0f)),
            SpatialShape.CONE to revolve(listOf(-.5f to 0f, -.5f to .5f, .5f to 0f)),
            SpatialShape.TORUS to revolve((0..8).map { index ->
                val angle = index * PI / 4
                (.12f * sin(angle).toFloat()) to (.36f + .12f * cos(angle).toFloat())
            }).let { mesh ->
                mesh.copy(vertices = mesh.vertices.map { SpatialVector(it.x, -it.z, it.y) })
            },
        )
    }

    private fun revolve(profile: List<Pair<Float, Float>>): SpatialMesh {
        val segments = 16
        val vertices = profile.flatMap { (y, radius) ->
            List(segments) { index ->
                val angle = index * 2 * PI / segments
                SpatialVector(radius * cos(angle).toFloat(), y, radius * sin(angle).toFloat())
            }
        }
        val faces = buildList {
            for (ring in 0 until profile.lastIndex) for (side in 0 until segments) {
                val next = (side + 1) % segments
                val low = ring * segments
                val high = low + segments
                add(intArrayOf(low + side, high + side, high + next, low + next))
            }
        }
        return SpatialMesh(vertices, faces)
    }

    fun bounds(experiment: ClassroomSpatialExperiment): Pair<SpatialVector, Float> {
        val ranges = experiment.objects.map { obj ->
            val orbit = obj.animation?.kind == SpatialAnimation.Kind.ORBIT
            val center = if (orbit) SpatialVector.Zero else obj.position
            val radius = subtreeRadius(obj) + if (orbit) obj.position.length() else 0f
            val extent = SpatialVector(radius, radius, radius)
            (center - extent) to (center + extent)
        }
        val min = SpatialVector(ranges.minOf { it.first.x }, ranges.minOf { it.first.y }, ranges.minOf { it.first.z })
        val max = SpatialVector(ranges.maxOf { it.second.x }, ranges.maxOf { it.second.y }, ranges.maxOf { it.second.z })
        val center = (min + max) * .5f
        val radius = ranges.maxOf { (low, high) -> ((low + high) * .5f - center).length() + (high.x - low.x) * .5f }
        return center to radius.coerceAtLeast(.01f)
    }

    private fun subtreeRadius(obj: SpatialObject): Float {
        val scale = maxOf(obj.scale.x, obj.scale.y, obj.scale.z)
        val children = obj.children.maxOfOrNull { it.position.length() + subtreeRadius(it) } ?: 0f
        val radius = maxOf(.87f, children) * scale
        return when (obj.animation?.kind) {
            SpatialAnimation.Kind.BOUNCE -> radius + .25f
            SpatialAnimation.Kind.PULSE -> radius * 1.12f
            else -> radius
        }
    }

    fun worldTransform(obj: SpatialObject, elapsed: Float): (SpatialVector) -> SpatialVector {
        val animation = obj.animation
        val phase = elapsed * (animation?.speed ?: 0f)
        var position = obj.position
        var scale = obj.scale
        var angles = obj.rotation
        when (animation?.kind) {
            SpatialAnimation.Kind.ROTATE -> angles += animation.axis * phase
            SpatialAnimation.Kind.ORBIT -> position = SpatialRotation(animation.axis * phase).apply(position)
            SpatialAnimation.Kind.BOUNCE -> position += animation.axis * (.25f * abs(sin(phase)))
            SpatialAnimation.Kind.PULSE -> scale *= 1f + .12f * sin(phase)
            null -> Unit
        }
        val rotation = SpatialRotation(angles)
        return { point -> rotation.apply(point.scaled(scale)) + position }
    }
}

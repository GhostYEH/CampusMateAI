package com.example.campusai.data.classroom.nativeplayer

import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

class ClassroomSpatialExperiment private constructor(
    val description: String,
    internal val objects: List<SpatialObject>,
    private val objectIds: Set<String>,
) {
    internal val animated = objects.any(SpatialObject::animated)

    internal fun supportsActions(actions: List<NativeAction>) = actions.none { action ->
        action.type.startsWith("widget_") &&
            (action.type != "widget_highlight" || objectId(action.widgetTarget) == null)
    }

    internal fun objectId(target: String?): String? =
        target?.takeIf { it.startsWith('#') }?.substring(1)?.takeIf(objectIds::contains)

    companion object {
        private const val Profile = "classroom-spatial/1"
        private val ObjectId = Regex("[A-Za-z_][A-Za-z0-9_-]{0,63}")
        private val HexColor = Regex("#[0-9a-fA-F]{6}")
        private val MaterialTypes = setOf("standard", "lambert", "phong", "basic", "emissive")

        internal fun fromWidgetConfig(raw: Any?): ClassroomSpatialExperiment? {
            val config = raw.asMap() ?: return null
            if (config["type"] != "visualization3d" || config["nativeRenderer"] != Profile) return null
            if (!config.only("type", "nativeRenderer", "description", "visualizationType", "objects", "interactions")) return null
            val description = (config["description"] as? String)?.trim()?.takeIf { it.length in 1..1500 } ?: return null
            val entries = config["interactions"].asList()?.takeIf { it.size == 2 } ?: return null
            val controls = entries.map { value ->
                val item = value.asMap() ?: return null
                if (!item.only("type", "target") || item["target"] != "camera") return null
                item["type"]
            }
            if (controls.toSet() != setOf("orbit", "zoom")) return null

            val ids = mutableSetOf<String>()
            val rawObjects = config["objects"].asList()?.takeIf { it.size in 1..16 } ?: return null
            val objects = rawObjects.map { parseObject(it, ids, 1) ?: return null }
            return ClassroomSpatialExperiment(description, objects, ids.toSet())
        }

        private fun parseObject(raw: Any?, ids: MutableSet<String>, depth: Int): SpatialObject? {
            if (depth > 3 || ids.size >= 16) return null
            val obj = raw.asMap() ?: return null
            if (!obj.only("id", "name", "type", "position", "rotation", "scale", "material", "animation", "children")) return null
            val id = (obj["id"] as? String)?.takeIf(ObjectId::matches) ?: return null
            if (!ids.add(id)) return null
            val label = (obj["name"] as? String)?.trim()?.takeIf { it.length in 1..80 } ?: return null
            val shape = SpatialShape.entries.firstOrNull { it.wireValue == obj["type"] } ?: return null
            val position = obj["position"]?.let { vector(it, -40f..40f) ?: return null } ?: SpatialVector.Zero
            val rotation = obj["rotation"]?.let { vector(it, -360f..360f) ?: return null } ?: SpatialVector.Zero
            val scale = obj["scale"]?.let { value ->
                number(value, .03f..12f)?.let { SpatialVector(it, it, it) }
                    ?: vector(value, .03f..12f) ?: return null
            } ?: SpatialVector.One
            val material = parseMaterial(obj["material"].asMap() ?: return null) ?: return null
            val motion = obj["animation"]?.let { parseAnimation(it.asMap() ?: return null) ?: return null }
            val children = obj["children"]?.let { value ->
                val list = value.asList()?.takeIf { it.size <= 16 } ?: return null
                list.map { parseObject(it, ids, depth + 1) ?: return null }
            }.orEmpty()
            return SpatialObject(id, label, shape, position, rotation, scale, material, motion, children)
        }

        private fun parseMaterial(map: Map<String, Any?>): SpatialMaterial? {
            if (!map.only("type", "color", "wireframe", "transparent", "opacity")) return null
            val type = map["type"] ?: "standard"
            if (type !in MaterialTypes) return null
            val hex = (map["color"] as? String)?.takeIf(HexColor::matches) ?: return null
            val wireframe = map["wireframe"]?.let { it as? Boolean ?: return null } ?: false
            val opacity = map["opacity"]?.let { number(it, .15f..1f) ?: return null } ?: 1f
            val transparent = map["transparent"]?.let { it as? Boolean ?: return null } ?: false
            if (opacity < 1f && !transparent) return null
            return SpatialMaterial(hex.substring(1).toInt(16), opacity, wireframe, type in setOf("basic", "emissive"))
        }

        private fun parseAnimation(map: Map<String, Any?>): SpatialAnimation? {
            if (!map.only("type", "speed", "axis")) return null
            val type = SpatialAnimation.Kind.entries.firstOrNull { it.wireValue == map["type"] } ?: return null
            val speed = map["speed"]?.let { number(it, .05f..6f) ?: return null } ?: 1f
            val axis = when (map["axis"] ?: "y") {
                "x" -> SpatialVector(1f, 0f, 0f)
                "y" -> SpatialVector(0f, 1f, 0f)
                "z" -> SpatialVector(0f, 0f, 1f)
                else -> return null
            }
            return SpatialAnimation(type, axis, speed)
        }

        private fun vector(raw: Any?, range: ClosedFloatingPointRange<Float>): SpatialVector? {
            val map = raw.asMap() ?: return null
            if (!map.only("x", "y", "z")) return null
            return SpatialVector(
                number(map["x"], range) ?: return null,
                number(map["y"], range) ?: return null,
                number(map["z"], range) ?: return null,
            )
        }

        private fun number(value: Any?, range: ClosedFloatingPointRange<Float>) =
            (value as? Number)?.toFloat()?.takeIf { it.isFinite() && it in range }

        private fun Map<String, Any?>.only(vararg fields: String) = keys.all { it in fields }
    }
}

internal enum class SpatialShape(val wireValue: String) {
    BOX("box"), SPHERE("sphere"), CYLINDER("cylinder"), CONE("cone"), TORUS("torus"), PLANE("plane"),
}

internal data class SpatialMaterial(val rgb: Int, val opacity: Float, val wireframe: Boolean, val unlit: Boolean)

internal data class SpatialAnimation(val kind: Kind, val axis: SpatialVector, val speed: Float) {
    enum class Kind(val wireValue: String) { ROTATE("rotate"), ORBIT("orbit"), BOUNCE("bounce"), PULSE("pulse") }
}

internal data class SpatialObject(
    val id: String,
    val label: String,
    val shape: SpatialShape,
    val position: SpatialVector,
    val rotation: SpatialVector,
    val scale: SpatialVector,
    val material: SpatialMaterial,
    val animation: SpatialAnimation?,
    val children: List<SpatialObject>,
) {
    val animated: Boolean get() = animation != null || children.any(SpatialObject::animated)
}

internal data class SpatialVector(val x: Float, val y: Float, val z: Float) {
    operator fun plus(other: SpatialVector) = SpatialVector(x + other.x, y + other.y, z + other.z)
    operator fun minus(other: SpatialVector) = SpatialVector(x - other.x, y - other.y, z - other.z)
    operator fun times(factor: Float) = SpatialVector(x * factor, y * factor, z * factor)
    fun scaled(factor: SpatialVector) = SpatialVector(x * factor.x, y * factor.y, z * factor.z)
    fun cross(other: SpatialVector) = SpatialVector(y * other.z - z * other.y, z * other.x - x * other.z, x * other.y - y * other.x)
    fun dot(other: SpatialVector) = x * other.x + y * other.y + z * other.z
    fun length() = sqrt(dot(this))

    companion object {
        val Zero = SpatialVector(0f, 0f, 0f)
        val One = SpatialVector(1f, 1f, 1f)
    }
}

/** Euler XYZ applies the coordinate-space Z turn first, matching the browser mesh. */
internal class SpatialRotation(angles: SpatialVector) {
    private val cx = cos(angles.x)
    private val sx = sin(angles.x)
    private val cy = cos(angles.y)
    private val sy = sin(angles.y)
    private val cz = cos(angles.z)
    private val sz = sin(angles.z)

    fun apply(point: SpatialVector): SpatialVector {
        val x = point.x * cz - point.y * sz
        val y = point.x * sz + point.y * cz
        val z = -x * sy + point.z * cy
        return SpatialVector(x * cy + point.z * sy, y * cx - z * sx, y * sx + z * cx)
    }
}

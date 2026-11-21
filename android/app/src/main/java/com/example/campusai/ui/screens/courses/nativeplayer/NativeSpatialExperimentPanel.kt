package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.CustomAccessibilityAction
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.customActions
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.ClassroomSpatialExperiment
import com.example.campusai.data.classroom.nativeplayer.ClassroomSpatialGeometry
import com.example.campusai.data.classroom.nativeplayer.SpatialObject
import com.example.campusai.data.classroom.nativeplayer.SpatialRotation
import com.example.campusai.data.classroom.nativeplayer.SpatialShape
import com.example.campusai.data.classroom.nativeplayer.SpatialVector
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.LocalReduceMotion
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.isActive
import kotlin.math.abs

private const val DefaultYaw = 35f
private const val DefaultPitch = 19f

@Composable
internal fun NativeSpatialExperimentPanel(
    experiment: ClassroomSpatialExperiment,
    highlighted: String?,
    modifier: Modifier = Modifier,
) {
    val reduceMotion = LocalReduceMotion.current
    var yaw by rememberSaveable { mutableFloatStateOf(DefaultYaw) }
    var pitch by rememberSaveable { mutableFloatStateOf(DefaultPitch) }
    var zoom by rememberSaveable { mutableFloatStateOf(1f) }
    var playing by rememberSaveable { mutableStateOf(experiment.animated && !reduceMotion) }
    var elapsed by rememberSaveable { mutableFloatStateOf(0f) }
    val bounds = remember(experiment) { ClassroomSpatialGeometry.bounds(experiment) }
    val highlightId = experiment.objectId(highlighted)
    LaunchedEffect(playing) {
        if (!playing) return@LaunchedEffect
        var previous = withFrameNanos { it }
        while (isActive) {
            val frame = withFrameNanos { it }
            if (frame - previous >= 30_000_000L) {
                elapsed += ((frame - previous) / 1_000_000_000f).coerceIn(0f, .10f)
                previous = frame
            }
        }
    }

    fun orbit(dx: Float, dy: Float) {
        yaw = (yaw + dx) % 360f
        pitch = (pitch + dy).coerceIn(-80f, 80f)
    }
    fun magnify(factor: Float) {
        zoom = (zoom * factor).coerceIn(.6f, 3f)
    }
    fun reset() {
        yaw = DefaultYaw
        pitch = DefaultPitch
        zoom = 1f
    }

    val frame = RoundedCornerShape(14.dp)
    val plot = RoundedCornerShape(10.dp)
    val grid = Line
    val accent = Primary
    BoxWithConstraints(modifier.clip(frame).background(Surface).border(1.dp, grid, frame).padding(12.dp)) {
        val wide = maxWidth >= 440.dp && maxHeight < 340.dp
        val canvasHeight = (maxHeight - 132.dp).coerceIn(136.dp, 330.dp)
        val model: @Composable (Modifier) -> Unit = { drawingModifier ->
            Canvas(drawingModifier.clip(plot)
                .background(Brush.verticalGradient(listOf(Background, Color(0xFF18323C))))
                .border(1.dp, grid, plot)
                .pointerInput(experiment) {
                    detectTransformGestures { _, pan, scale, _ ->
                        orbit(pan.x / density * .44f, -pan.y / density * .44f)
                        magnify(scale)
                    }
                }
                .semantics {
                    contentDescription = "原生三维模型"
                    customActions = listOf(
                        CustomAccessibilityAction("水平旋转") {
                            orbit(25f, 0f)
                            true
                        },
                        CustomAccessibilityAction("垂直旋转") {
                            orbit(0f, 18f)
                            true
                        },
                    )
                },
            ) {
                val radians = (Math.PI / 180).toFloat()
                val view = SpatialRotation(SpatialVector(pitch * radians, yaw * radians, 0f))
                val light = SpatialVector(-.32f, .56f, .76f)
                val scale = size.minDimension * .43f * zoom
                val (worldOrigin, radius) = bounds
                val time = elapsed
                fun screen(point: SpatialVector): Offset {
                    val perspective = 3.6f / (3.6f - point.z)
                    return center + Offset(point.x * scale * perspective, -point.y * scale * perspective)
                }
                fun viewPoint(point: SpatialVector) = view.apply((point - worldOrigin) * (1f / radius))
                fun gridPoint(x: Float, z: Float) = screen(view.apply(SpatialVector(x, -.65f, z)))
                for (step in -4..4) {
                    val axis = step * .20f
                    drawLine(grid.copy(alpha = .52f), gridPoint(-.8f, axis), gridPoint(.8f, axis), .65.dp.toPx())
                    drawLine(grid.copy(alpha = .52f), gridPoint(axis, -.8f), gridPoint(axis, .8f), .65.dp.toPx())
                }

                val faces = mutableListOf<SpatialFace>()
                var selectedPoint: Offset? = null
                fun collect(obj: SpatialObject, parent: (SpatialVector) -> SpatialVector) {
                    val transform = ClassroomSpatialGeometry.worldTransform(obj, time)
                    fun world(point: SpatialVector) = parent(transform(point))
                    val mesh = ClassroomSpatialGeometry.meshes.getValue(obj.shape)
                    val vertices = mesh.vertices.map { viewPoint(world(it)) }
                    val projected = vertices.map(::screen)
                    val selected = obj.id == highlightId
                    if (selected) selectedPoint = screen(viewPoint(world(SpatialVector.Zero)))
                    val tint = Color(0xFF000000.toInt() or obj.material.rgb)
                    for (indices in mesh.faces) {
                        val a = vertices[indices[0]]
                        val b = vertices[indices[1]]
                        val c = vertices[indices[2]]
                        var normal = (b - a).cross(c - a)
                        if (normal.length() < 1e-7f && indices.size == 4) {
                            normal = (c - a).cross(vertices[indices[3]] - a)
                        }
                        val length = normal.length()
                        if (length < 1e-7f) continue
                        val material = obj.material
                        if (normal.z < 0f && !material.wireframe && material.opacity == 1f && obj.shape != SpatialShape.PLANE) continue
                        val shade = .44f + .56f * abs(normal.dot(light) / length).coerceAtMost(1f)
                        val color = (if (material.unlit || material.wireframe) tint else lerp(Color.Black, tint, shade))
                            .copy(alpha = material.opacity)
                        val depth = indices.sumOf { vertices[it].z.toDouble() }.toFloat() / indices.size
                        faces.add(SpatialFace(indices, projected, depth, color, material.wireframe, selected))
                    }
                    obj.children.forEach { collect(it, ::world) }
                }
                experiment.objects.forEach { collect(it) { point -> point } }
                faces.sortBy { it.depth }
                val path = Path()
                for (face in faces) {
                    path.reset()
                    val first = face.points[face.indices[0]]
                    path.moveTo(first.x, first.y)
                    for (index in 1 until face.indices.size) {
                        val vertex = face.points[face.indices[index]]
                        path.lineTo(vertex.x, vertex.y)
                    }
                    path.close()
                    if (!face.wireframe) drawPath(path, face.color)
                    if (face.highlighted || face.wireframe) {
                        drawPath(path, if (face.highlighted) accent else face.color, style = Stroke(1.dp.toPx()))
                    }
                }
                selectedPoint?.let { drawCircle(accent, 8.dp.toPx(), it, style = Stroke(1.dp.toPx())) }
            }
        }
        val controls: @Composable (Modifier) -> Unit = { controlModifier ->
            Column(controlModifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { magnify(1f / 1.2f) }) { Icon(Icons.Default.Remove, "缩小模型", tint = Accent) }
                    IconButton(onClick = { magnify(1.2f) }) { Icon(Icons.Default.Add, "放大模型", tint = Accent) }
                    IconButton(onClick = ::reset) { Icon(Icons.Default.Refresh, "重置视角", tint = Accent) }
                    if (!wide && experiment.animated) {
                        Button(onClick = { playing = !playing }) { Text(if (playing) "暂停动画" else "播放动画") }
                    }
                }
                if (wide && experiment.animated) {
                    Button(onClick = { playing = !playing }) { Text(if (playing) "暂停动画" else "播放动画") }
                }
                Text("拖动旋转，双指缩放", color = Muted, fontSize = 12.sp)
                experiment.objects.labelFor(highlightId)?.let { label ->
                    Text("老师正在指示 " + label, color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
                Text(experiment.description, color = TextPrimary, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }
        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                model(Modifier.weight(1.6f).fillMaxHeight())
                controls(Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()))
            }
        } else {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                model(Modifier.fillMaxWidth().height(canvasHeight))
                controls(Modifier.fillMaxWidth())
            }
        }
    }
}

private data class SpatialFace(
    val indices: IntArray,
    val points: List<Offset>,
    val depth: Float,
    val color: Color,
    val wireframe: Boolean,
    val highlighted: Boolean,
)

private fun List<SpatialObject>.labelFor(target: String?): String? {
    if (target == null) return null
    for (obj in this) {
        if (obj.id == target) return obj.label
        obj.children.labelFor(target)?.let { return it }
    }
    return null
}

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
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.isActive
import kotlin.math.abs

private const val DefaultYaw = 35f
private const val DefaultPitch = 19f

internal class NativeSpatialControls(playAnimation: Boolean) {
    var yaw by mutableFloatStateOf(DefaultYaw)
        private set
    var pitch by mutableFloatStateOf(DefaultPitch)
        private set
    var zoom by mutableFloatStateOf(1f)
        private set
    var playing by mutableStateOf(playAnimation)
    var elapsed by mutableFloatStateOf(0f)

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
}

@Composable
internal fun NativeSpatialExperimentPanel(
    experiment: ClassroomSpatialExperiment,
    spatialControls: NativeSpatialControls,
    playAnimation: Boolean,
    highlighted: String?,
    modifier: Modifier = Modifier,
) {
    val bounds = remember(experiment) { ClassroomSpatialGeometry.bounds(experiment) }
    val highlightId = experiment.highlightedObject(highlighted)
    LaunchedEffect(spatialControls, playAnimation) {
        spatialControls.playing = playAnimation
    }
    LaunchedEffect(spatialControls, spatialControls.playing) {
        if (!spatialControls.playing) return@LaunchedEffect
        var previous = withFrameNanos { it }
        while (isActive) {
            val frame = withFrameNanos { it }
            if (frame - previous >= 30_000_000L) {
                spatialControls.elapsed += ((frame - previous) / 1_000_000_000f).coerceIn(0f, .10f)
                previous = frame
            }
        }
    }

    val frame = RoundedCornerShape(14.dp)
    val viewport = RoundedCornerShape(10.dp)
    val grid = Line
    val highlightColor = Primary
    BoxWithConstraints(modifier.clip(frame).background(Surface).border(1.dp, grid, frame).padding(12.dp)) {
        val wide = maxWidth >= 440.dp && maxHeight < 340.dp
        val sceneHeight = (maxHeight - 132.dp).coerceIn(136.dp, 330.dp)
        val model: @Composable (Modifier) -> Unit = { canvasModifier ->
            Canvas(
                canvasModifier.clip(viewport)
                    .background(Brush.verticalGradient(listOf(Background, Color(0xFF18323C))))
                    .border(1.dp, grid, viewport)
                    .pointerInput(experiment, spatialControls) {
                        detectTransformGestures { _, pan, scale, _ ->
                            // The pan component of the touch gesture turns the camera around the model.
                            spatialControls.orbit(pan.x / density * .44f, -pan.y / density * .44f)
                            spatialControls.magnify(scale)
                        }
                    }
                    .semantics {
                        contentDescription = "原生三维模型"
                        customActions = listOf(
                            CustomAccessibilityAction("水平旋转") {
                                spatialControls.orbit(25f, 0f)
                                true
                            },
                            CustomAccessibilityAction("垂直旋转") {
                                spatialControls.orbit(0f, 18f)
                                true
                            },
                        )
                    },
            ) {
                val radians = (Math.PI / 180).toFloat()
                val view = SpatialRotation(
                    SpatialVector(spatialControls.pitch * radians, spatialControls.yaw * radians, 0f),
                )
                val light = SpatialVector(-.32f, .56f, .76f)
                val scale = size.minDimension * .43f * spatialControls.zoom
                val worldOrigin = bounds.first
                val worldScale = 1f / bounds.second
                fun project(point: SpatialVector): Offset {
                    val perspective = 3.6f / (3.6f - point.z)
                    return center + Offset(point.x * scale * perspective, -point.y * scale * perspective)
                }
                fun viewportPoint(point: SpatialVector) = view.apply((point - worldOrigin) * worldScale)
                val guideColor = grid.copy(alpha = .52f)
                fun gridPoint(x: Float, z: Float) = project(view.apply(SpatialVector(x, -.65f, z)))
                for (step in -4..4) {
                    val axis = step * .20f
                    drawLine(guideColor, gridPoint(-.80f, axis), gridPoint(.80f, axis), .65.dp.toPx())
                    drawLine(guideColor, gridPoint(axis, -.80f), gridPoint(axis, .80f), .65.dp.toPx())
                }

                val time = spatialControls.elapsed
                val faces = mutableListOf<ProjectedSpatialFace>()
                var selectedAt: Offset? = null
                fun collectFaces(obj: SpatialObject, toWorld: (SpatialVector) -> SpatialVector) {
                    val localPose = ClassroomSpatialGeometry.worldTransform(obj, time)
                    fun world(point: SpatialVector) = toWorld(localPose(point))
                    val mesh = ClassroomSpatialGeometry.meshes.getValue(obj.shape)
                    val vertices = mesh.vertices.map { viewportPoint(world(it)) }
                    val projected = vertices.map(::project)
                    val selected = obj.id == highlightId
                    if (selected) {
                        selectedAt = project(viewportPoint(world(SpatialVector.Zero)))
                    }
                    val tint = Color(0xFF000000.toInt() or obj.material.rgb)
                    for (face in mesh.faces) {
                        val first = vertices[face[0]]
                        val second = vertices[face[1]]
                        val third = vertices[face[2]]
                        var normal = (second - first).cross(third - first)
                        if (normal.length() < 1e-7f && face.size == 4) {
                            normal = (third - first).cross(vertices[face[3]] - first)
                        }
                        if (normal.length() < 1e-7f) continue
                        if (normal.z < 0f && !obj.material.wireframe && obj.material.opacity == 1f && obj.shape != SpatialShape.PLANE) continue
                        val lit = .47f + .53f * abs(normal.dot(light) / normal.length()).coerceAtMost(1f)
                        val color = if (obj.material.unlit || obj.material.wireframe) tint else lerp(Color.Black, tint, lit)
                        val depth = face.sumOf { vertices[it].z.toDouble() }.toFloat() / face.size
                        faces.add(ProjectedSpatialFace(face, projected, depth, color.copy(alpha = obj.material.opacity), obj.material.wireframe, selected))
                    }
                    obj.children.forEach { collectFaces(it, ::world) }
                }
                experiment.objects.forEach { collectFaces(it) { point -> point } }
                faces.sortBy { it.depth }
                val path = Path()
                for (face in faces) {
                    val first = face.points[face.indices[0]]
                    path.reset()
                    path.moveTo(first.x, first.y)
                    for (index in 1 until face.indices.size) {
                        val vertex = face.points[face.indices[index]]
                        path.lineTo(vertex.x, vertex.y)
                    }
                    path.close()
                    if (!face.wireframe) drawPath(path, face.color)
                    if (face.wireframe || face.highlighted) {
                        drawPath(path, if (face.highlighted) highlightColor else face.color, style = Stroke(1.dp.toPx()))
                    }
                }
                selectedAt?.let { point ->
                    drawCircle(highlightColor.copy(alpha = .65f), 9.dp.toPx(), point, style = Stroke(1.1.dp.toPx()))
                }
            }
        }
        val controls: @Composable (Modifier) -> Unit = { controlModifier ->
            Column(controlModifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(horizontalArrangement = Arrangement.spacedBy(3.dp), verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { spatialControls.magnify(1f / 1.2f) }) { Icon(Icons.Default.Remove, "缩小模型", tint = Accent) }
                    IconButton(onClick = { spatialControls.magnify(1.2f) }) { Icon(Icons.Default.Add, "放大模型", tint = Accent) }
                    IconButton(onClick = spatialControls::reset) { Icon(Icons.Default.Refresh, "重置视角", tint = Accent) }
                    if (!wide && experiment.animated) SpatialAnimationButton(spatialControls)
                }
                if (wide && experiment.animated) SpatialAnimationButton(spatialControls)
                Text("拖动旋转，双指缩放", color = Muted, fontSize = 12.sp)
                experiment.objects.labelFor(highlightId)?.let { label ->
                    Text("老师正在指示 $label", color = Primary, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                }
                Text(experiment.description, color = TextPrimary, fontSize = 13.sp, lineHeight = 19.sp)
            }
        }
        if (wide) {
            Row(Modifier.fillMaxSize(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                model(Modifier.weight(1.5f).fillMaxHeight())
                controls(Modifier.weight(1f).fillMaxHeight().verticalScroll(rememberScrollState()))
            }
        } else {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                model(Modifier.fillMaxWidth().height(sceneHeight))
                controls(Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun SpatialAnimationButton(controls: NativeSpatialControls) {
    Button(onClick = { controls.playing = !controls.playing }) {
        Text(if (controls.playing) "暂停动画" else "播放动画")
    }
}

private data class ProjectedSpatialFace(
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
        if (obj.id == target) return obj.name
        obj.children.labelFor(target)?.let { return it }
    }
    return null
}

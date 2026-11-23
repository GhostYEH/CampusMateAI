package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import coil.ImageLoader
import com.example.campusai.BuildConfig
import com.example.campusai.data.classroom.nativeplayer.NativeCanvasElement
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomAssetPolicy
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomText
import com.example.campusai.data.classroom.nativeplayer.NativeSlide
import com.example.campusai.ui.theme.Muted
import java.util.Locale
import kotlin.math.max

/**
 * 1000×562.5 的课堂画布。坐标、尺寸、旋转全部按原文档比例映射，
 * 文字/图片/公式/表格/图表都按文档顺序叠放，不做重排。
 */
@Composable
fun NativeSlideCanvas(
    slide: NativeSlide,
    imageLoader: ImageLoader,
    modifier: Modifier = Modifier,
    spotlightElementId: String? = null,
    laserElementId: String? = null,
    onVideoClick: (NativeCanvasElement.Video) -> Unit = {},
    onAudioClick: (String) -> Unit = {},
    assetKeyPrefix: String = "",
    /** 当前课堂 media 接口前缀；用于相对路径与 /media/media/ 拼接。 */
    mediaBase: String? = null,
    isPreview: Boolean = false,
) {
    val context = LocalContext.current
    val presentation = remember(slide) { classroomSlideTemplate(slide) }
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Color(0xFFFDFBF2)),
    ) {
        // 背景单独铺一层，文字和元素不参与背景图缩放。
        Box(Modifier.fillMaxSize()) {
            val gradient = presentation.background.gradientColors
            when {
                gradient.size >= 2 -> Box(
                    Modifier
                        .fillMaxSize()
                        .background(Brush.linearGradient(gradient.map(::parseCssColor))),
                )
                !presentation.background.color.isNullOrBlank() -> Box(
                    Modifier
                        .fillMaxSize()
                        .background(parseCssColor(presentation.background.color)),
                )
            }
            val backgroundUrl = NativeClassroomAssetPolicy.resolve(
                presentation.background.imageUrl,
                BuildConfig.API_BASE_URL,
                mediaBase,
            )
            if (backgroundUrl != null) {
                AsyncImage(
                    model = cachedImageRequest(context, backgroundUrl, assetKeyPrefix, "background"),
                    imageLoader = imageLoader,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }

        BoxWithConstraints(
            modifier = Modifier.fillMaxWidth(),
        ) {
            val canvasHeight = (maxWidth.value / slide.aspectRatio).dp
            val unit = maxWidth.value / slide.viewportSize.toFloat()
            fun px(value: Double): androidx.compose.ui.unit.Dp = (value.toFloat() * unit).dp
            Box(Modifier.fillMaxWidth().height(canvasHeight)) {
                presentation.elements.forEach { element ->
                    val highlighted = element.id == spotlightElementId || element.id == laserElementId
                    val dimmed = spotlightElementId != null && !highlighted
                    Box(
                        modifier = Modifier
                            .offset(x = px(element.left), y = px(element.top))
                            .size(width = px(element.width).coerceAtLeast(1.dp), height = px(element.height).coerceAtLeast(1.dp))
                            .graphicsLayer(rotationZ = element.rotate.toFloat())
                            .alpha(if (dimmed) 0.32f else element.opacity.toFloat().coerceIn(0f, 1f)),
                    ) {
                        when (element) {
                            is NativeCanvasElement.Text -> CanvasText(element, unit)
                            is NativeCanvasElement.Shape -> CanvasShape(element, unit)
                            is NativeCanvasElement.Line -> CanvasLine(element)
                            is NativeCanvasElement.Image ->
                                CanvasImage(element, imageLoader, assetKeyPrefix, mediaBase, isPreview)
                            is NativeCanvasElement.Video ->
                                CanvasVideo(element, imageLoader, onVideoClick, assetKeyPrefix, mediaBase, isPreview)
                            is NativeCanvasElement.Table -> CanvasTable(element)
                            is NativeCanvasElement.Chart -> CanvasChart(element)
                            is NativeCanvasElement.Latex -> Text(
                                text = NativeClassroomText.readableFormula(element.latex),
                                color = parseCssColor(element.color),
                                fontSize = ((element.fontSize ?: 24.0) * unit).sp,
                                fontStyle = FontStyle.Italic,
                                modifier = Modifier.fillMaxSize(),
                            )
                            is NativeCanvasElement.Audio -> {
                                val play = if (isPreview) Modifier else Modifier.clickable { onAudioClick(element.source) }
                                Box(
                                    Modifier.fillMaxSize().clip(RoundedCornerShape(8.dp))
                                        .background(Color(0xFFE4EEE5)).then(play),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Text("播放本页音频", color = Color(0xFF285B4B), fontSize = 12.sp)
                                }
                            }
                            is NativeCanvasElement.Unknown -> Box(
                                Modifier
                                    .fillMaxSize()
                                    .border(1.dp, Muted.copy(alpha = 0.5f), RoundedCornerShape(4.dp)),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text("未识别元素 ${element.type}", color = Muted, fontSize = 10.sp)
                            }
                        }
                        if (highlighted) {
                            Box(
                                Modifier
                                    .fillMaxSize()
                                    .border(3.dp, Color(0xFFE08A4E), RoundedCornerShape(6.dp)),
                            )
                        }
                        if (element.id == laserElementId) {
                            Box(
                                Modifier
                                    .align(Alignment.Center)
                                    .size(14.dp)
                                    .clip(RoundedCornerShape(7.dp))
                                    .background(Color(0xFFD94A4A)),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CanvasText(element: NativeCanvasElement.Text, unit: Float) {
    val fontSize = (element.fontSize ?: 20.0).toFloat() * unit
    Text(
        text = element.plainText,
        color = parseCssColor(element.fontColor),
        fontSize = fontSize.sp,
        fontWeight = if (element.bold) FontWeight.Bold else FontWeight.Normal,
        fontStyle = if (element.italic) FontStyle.Italic else FontStyle.Normal,
        textDecoration = if (element.underline) TextDecoration.Underline else null,
        textAlign = when (element.align.lowercase(Locale.ROOT)) {
            "center" -> TextAlign.Center
            "right" -> TextAlign.End
            "justify" -> TextAlign.Justify
            else -> TextAlign.Start
        },
        style = TextStyle(lineHeight = (fontSize * element.lineHeight.toFloat()).sp),
        modifier = Modifier.fillMaxSize(),
    )
}

@Composable
private fun CanvasShape(element: NativeCanvasElement.Shape, unit: Float) {
    Box(Modifier.fillMaxSize()) {
        androidx.compose.foundation.Canvas(Modifier.fillMaxSize()) {
            val fill = element.fill?.let(::parseCssColor)
            val stroke = element.stroke?.let(::parseCssColor)
            val strokeWidth = element.strokeWidth.toFloat().coerceAtLeast(0f)
            val corner = element.radius.toFloat()
            when (element.shapeType.lowercase(Locale.ROOT)) {
                "ellipse", "circle" -> {
                    fill?.let { drawCircle(it, radius = size.minDimension / 2f) }
                    stroke?.let { drawCircle(it, radius = size.minDimension / 2f, style = Stroke(strokeWidth)) }
                }
                "triangle" -> {
                    val path = Path().apply {
                        moveTo(size.width / 2f, 0f)
                        lineTo(size.width, size.height)
                        lineTo(0f, size.height)
                        close()
                    }
                    fill?.let { drawPath(path, it) }
                    stroke?.let { drawPath(path, it, style = Stroke(strokeWidth)) }
                }
                else -> {
                    fill?.let { drawRoundRect(it, Offset.Zero, Size(size.width, size.height), CornerRadius(corner)) }
                    stroke?.let {
                        drawRoundRect(
                            it,
                            Offset.Zero,
                            Size(size.width, size.height),
                            CornerRadius(corner),
                            style = Stroke(strokeWidth),
                        )
                    }
                }
            }
        }
        element.text?.let { shapeText ->
            if (shapeText.plainText.isNotBlank()) {
                val anchor = when (shapeText.verticalAlign.lowercase(Locale.ROOT)) {
                    "top" -> Alignment.TopStart
                    "bottom" -> Alignment.BottomStart
                    else -> Alignment.CenterStart
                }
                val fontSize = ((shapeText.fontSize ?: 18.0).toFloat() * unit).coerceAtLeast(1f)
                Text(
                    text = shapeText.plainText,
                    color = parseCssColor(shapeText.fontColor),
                    fontSize = fontSize.sp,
                    fontWeight = if (shapeText.bold) FontWeight.Bold else FontWeight.Normal,
                    fontStyle = if (shapeText.italic) FontStyle.Italic else FontStyle.Normal,
                    textDecoration = if (shapeText.underline) TextDecoration.Underline else null,
                    textAlign = when (shapeText.align.lowercase(Locale.ROOT)) {
                        "center" -> TextAlign.Center
                        "right" -> TextAlign.End
                        "justify" -> TextAlign.Justify
                        else -> TextAlign.Start
                    },
                    style = TextStyle(lineHeight = (fontSize * shapeText.lineHeight.toFloat()).sp),
                    modifier = Modifier.align(anchor).fillMaxWidth().padding(4.dp),
                )
            }
        }
    }
}

@Composable
private fun CanvasLine(element: NativeCanvasElement.Line) {
    androidx.compose.foundation.Canvas(Modifier.fillMaxSize()) {
        val start = if (element.startX != 0.0 || element.startY != 0.0) {
            Offset(element.startX.toFloat(), element.startY.toFloat())
        } else {
            Offset(0f, 0f)
        }
        val end = if (element.endX != 0.0 || element.endY != 0.0) {
            Offset(element.endX.toFloat(), element.endY.toFloat())
        } else {
            Offset(size.width, size.height)
        }
        drawLine(
            color = parseCssColor(element.color),
            start = start,
            end = end,
            strokeWidth = element.strokeWidth.toFloat().coerceAtLeast(1f),
        )
    }
}

@Composable
private fun CanvasImage(
    element: NativeCanvasElement.Image,
    imageLoader: ImageLoader,
    assetKeyPrefix: String,
    mediaBase: String?,
    isPreview: Boolean,
) {
    ClassroomRemoteImage(
        url = NativeClassroomAssetPolicy.resolve(element.source, BuildConfig.API_BASE_URL, mediaBase),
        imageLoader = imageLoader,
        assetKeyPrefix = assetKeyPrefix,
        slot = "image-${element.id}",
        contentScale = ContentScale.Fit,
        isPreview = isPreview,
        modifier = Modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(element.radius.dp)),
    )
}

@Composable
private fun ClassroomRemoteImage(
    url: String?,
    imageLoader: ImageLoader,
    assetKeyPrefix: String,
    slot: String,
    contentScale: ContentScale,
    isPreview: Boolean,
    modifier: Modifier = Modifier,
) {
    if (url == null) {
        Box(
            modifier.background(Color(0xFFE7E9E2)),
            contentAlignment = Alignment.Center,
        ) {
            Text("图片资源未下发", color = Muted, fontSize = 10.sp)
        }
        return
    }
    val context = LocalContext.current
    var attempt by remember(url) { mutableIntStateOf(0) }
    var failed by remember(url, attempt) { mutableStateOf(false) }
    Box(modifier) {
        if (failed) {
            val retry = if (isPreview) Modifier else Modifier.clickable {
                failed = false
                attempt++
            }
            Column(
                Modifier
                    .fillMaxSize()
                    .background(Color(0xFFE7E9E2))
                    .then(retry),
                verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("图片加载失败", color = Muted, fontSize = 10.sp)
                if (!isPreview) Text("点击重试", color = Color(0xFF285B4B), fontSize = 10.sp)
            }
        } else {
            key(attempt) {
                AsyncImage(
                    model = cachedImageRequest(context, url, assetKeyPrefix, slot),
                    imageLoader = imageLoader,
                    contentDescription = null,
                    contentScale = contentScale,
                    onError = { failed = true },
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
    }
}

@Composable
private fun CanvasVideo(
    element: NativeCanvasElement.Video,
    imageLoader: ImageLoader,
    onClick: (NativeCanvasElement.Video) -> Unit,
    assetKeyPrefix: String,
    mediaBase: String?,
    isPreview: Boolean,
) {
    val context = LocalContext.current
    val poster = NativeClassroomAssetPolicy.resolve(element.poster, BuildConfig.API_BASE_URL, mediaBase)
    val play = if (isPreview) Modifier else Modifier.clickable { onClick(element) }
    Box(
        Modifier
            .fillMaxSize()
            .clip(RoundedCornerShape(8.dp))
            .background(Color(0xFF16202A))
            .then(play),
        contentAlignment = Alignment.Center,
    ) {
        if (poster != null) {
            AsyncImage(
                model = cachedImageRequest(context, poster, assetKeyPrefix, "poster-${element.id}"),
                imageLoader = imageLoader,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
        Text("▶", color = Color.White, fontSize = 28.sp)
    }
}

@Composable
private fun CanvasTable(element: NativeCanvasElement.Table) {
    val textColor = parseCssColor(element.textColor)
    Column(
        Modifier
            .fillMaxSize()
            .border(1.dp, parseCssColor(element.borderColor), RoundedCornerShape(4.dp)),
    ) {
        element.rows.forEachIndexed { rowIndex, row ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .background(if (rowIndex == 0) parseCssColor(element.headerFill) else Color.Transparent),
            ) {
                row.cells.forEach { cell ->
                    Text(
                        text = cell.text,
                        color = cell.color?.let(::parseCssColor) ?: textColor,
                        fontSize = 10.sp,
                        fontWeight = if (cell.bold || rowIndex == 0) FontWeight.SemiBold else FontWeight.Normal,
                        textAlign = when (cell.align) {
                            "center" -> TextAlign.Center
                            "right" -> TextAlign.End
                            else -> TextAlign.Start
                        },
                        modifier = Modifier
                            .weight(cell.colspan.toFloat().coerceAtLeast(1f))
                            .fillMaxSize()
                            .border(0.5.dp, parseCssColor(element.borderColor).copy(alpha = 0.5f))
                            .padding(4.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun CanvasChart(element: NativeCanvasElement.Chart) {
    val palette = element.colors.map(::parseCssColor).ifEmpty {
        listOf(Color(0xFF285B4B), Color(0xFFE08A4E), Color(0xFF6B8FB5), Color(0xFFC25450))
    }
    val labels = element.labels
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth()) {
            labels.forEach { label ->
                Text(
                    label,
                    color = parseCssColor(element.textColor),
                    fontSize = 8.sp,
                    maxLines = 1,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.weight(1f),
                )
            }
        }
        androidx.compose.foundation.Canvas(Modifier.fillMaxWidth().weight(1f)) {
            val maxValue = element.series.flatMap { it }.maxOrNull()?.takeIf { it > 0.0 } ?: 1.0
            val type = element.chartType.lowercase(Locale.ROOT)
            if (type.contains("pie") || type.contains("doughnut")) {
                val values = element.series.firstOrNull().orEmpty()
                val total = values.sum().takeIf { it > 0.0 } ?: 1.0
                var startAngle = -90f
                values.forEachIndexed { index, value ->
                    val sweep = (value / total * 360f).toFloat()
                    drawArc(
                        color = palette[index % palette.size],
                        startAngle = startAngle,
                        sweepAngle = sweep,
                        useCenter = true,
                    )
                    startAngle += sweep
                }
            } else if (type.contains("line")) {
                element.series.forEachIndexed { seriesIndex, values ->
                    val points = values.mapIndexed { index, value ->
                        Offset(
                            x = if (values.size <= 1) 0f else size.width * index / (values.size - 1),
                            y = size.height - (value / maxValue * size.height).toFloat(),
                        )
                    }
                    points.zipWithNext().forEach { (a, b) ->
                        drawLine(palette[seriesIndex % palette.size], a, b, strokeWidth = 2f)
                    }
                    points.forEach { point ->
                        drawCircle(palette[seriesIndex % palette.size], radius = 3f, center = point)
                    }
                }
            } else {
                val groupWidth = if (labels.isEmpty()) size.width else size.width / labels.size
                val seriesCount = max(1, element.series.size)
                val barWidth = groupWidth / (seriesCount + 1)
                element.series.forEachIndexed { seriesIndex, values ->
                    values.forEachIndexed { index, value ->
                        val left = index * groupWidth + barWidth * (seriesIndex + 0.5f)
                        val height = (value / maxValue * size.height).toFloat()
                        drawRect(
                            color = palette[seriesIndex % palette.size],
                            topLeft = Offset(left, size.height - height),
                            size = Size(barWidth, height),
                        )
                    }
                }
            }
        }
    }
}

private fun cachedImageRequest(
    context: android.content.Context,
    url: String,
    assetKeyPrefix: String,
    slot: String,
): ImageRequest {
    val cacheKey = "$assetKeyPrefix:$slot:$url"
    return ImageRequest.Builder(context)
        .data(url)
        .crossfade(false)
        .memoryCacheKey(cacheKey)
        .diskCacheKey(cacheKey)
        .build()
}

fun parseCssColor(raw: String?): Color {
    val value = raw?.trim().orEmpty()
    if (value.isBlank()) return Color(0xFF1B2730)
    if (value.startsWith("rgba(", ignoreCase = true) || value.startsWith("rgb(", ignoreCase = true)) {
        val numbers = value.substringAfter("(").substringBefore(")").split(",").map { it.trim() }
        val r = numbers.getOrNull(0)?.toFloatOrNull()?.coerceIn(0f, 255f) ?: 0f
        val g = numbers.getOrNull(1)?.toFloatOrNull()?.coerceIn(0f, 255f) ?: 0f
        val b = numbers.getOrNull(2)?.toFloatOrNull()?.coerceIn(0f, 255f) ?: 0f
        val a = numbers.getOrNull(3)?.toFloatOrNull()?.coerceIn(0f, 1f) ?: 1f
        return Color(r / 255f, g / 255f, b / 255f, a)
    }
    val hex = value.removePrefix("#")
    return runCatching {
        when (hex.length) {
            3 -> Color(
                (hex[0].digitToInt(16) * 17) / 255f,
                (hex[1].digitToInt(16) * 17) / 255f,
                (hex[2].digitToInt(16) * 17) / 255f,
            )
            6 -> Color(("FF$hex").toLong(16))
            8 -> Color(hex.toLong(16))
            else -> Color(0xFF1B2730)
        }
    }.getOrDefault(Color(0xFF1B2730))
}

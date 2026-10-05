package com.example.campusai.ui.screens.focus

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.GenericShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import com.example.campusai.BuildConfig
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.ui.screens.courses.formatClassroomStudyDuration
import java.time.LocalDate
import java.time.ZoneId

private val Night = Color(0xFF101E32)
private val Mist = Color(0xFFB7C8D2)
private val Cream = Color(0xFFF9EED9)
private val Amber = Color(0xFFDAB27A)
private val Coral = Color(0xFFD48F70)
private val Lake = Color(0xFF8FB4C2)

private data class TrailMoment(
    val id: String,
    val date: String,
    val time: String,
    val classroom: ClassroomFootprint? = null,
    val focus: FocusRecord? = null,
    val briefFocus: List<FocusRecord> = emptyList(),
)

private fun classroomMoment(entry: ClassroomFootprint): TrailMoment {
    val stamp = (entry.enteredAt ?: entry.item.createdAt).classroomTimeLabel()
    return TrailMoment(
        id = "classroom:${entry.item.sessionId ?: entry.item.url}",
        date = stamp.take(10).takeIf { it.matches(Regex("\\d{4}-\\d{2}-\\d{2}")) } ?: "0000-00-00",
        time = stamp.drop(11).take(5),
        classroom = entry,
    )
}

/** Mix both record sources by local date and time. Adjacent sub-minute focus attempts stay expandable. */
private fun trailMoments(records: List<FocusRecord>, classrooms: List<ClassroomFootprint>): List<TrailMoment> {
    val sorted = (classrooms.map(::classroomMoment) + records.map {
        TrailMoment("focus:${it.sourceId}", it.date, it.endedAt.take(5), focus = it)
    }).sortedWith(compareByDescending<TrailMoment> { it.date }.thenByDescending { it.time })
    val result = mutableListOf<TrailMoment>()
    var cursor = 0
    while (cursor < sorted.size) {
        val first = sorted[cursor]
        if (first.focus?.let { it.actualMinutes == 0 && it.mode == FocusMode.FOCUS.name } == true) {
            var end = cursor + 1
            while (end < sorted.size && sorted[end].date == first.date &&
                sorted[end].focus?.let { it.actualMinutes == 0 && it.mode == FocusMode.FOCUS.name } == true) end++
            if (end - cursor > 1) {
                result += first.copy(id = "brief:${first.date}:${first.id}", focus = null,
                    briefFocus = sorted.subList(cursor, end).mapNotNull { it.focus })
                cursor = end
                continue
            }
        }
        result += first
        cursor++
    }
    return result
}

@Composable
internal fun LearningFootprintContent(
    records: List<FocusRecord>,
    classrooms: List<ClassroomFootprint>,
    historyLoading: Boolean,
    selectedRecordId: String?,
    trustedOrigin: String?,
    onSelect: (String?) -> Unit,
    onBack: () -> Unit,
    onOpenClassroom: (String) -> Unit,
) {
    val moments = remember(records, classrooms) { trailMoments(records, classrooms) }
    val days = remember(moments) { moments.groupBy { it.date }.toList() }
    val selectedFocus = records.firstOrNull { "focus:${it.sourceId}" == selectedRecordId }
    val selectedClassroom = classrooms.firstOrNull { "classroom:${it.item.sessionId ?: it.item.url}" == selectedRecordId }
    val today = remember { LocalDate.now(ZoneId.systemDefault()).toString() }
    val todayFocusMinutes = records.filter { it.date == today }.sumOf { it.actualMinutes }
    val todayClassrooms = classrooms.filter { classroomMoment(it).date == today }
    val todayClassSeconds = todayClassrooms.sumOf { entry -> entry.visits.sumOf { it.activeSeconds } }
    val bottomPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 28.dp
    val listState = rememberLazyListState()
    LaunchedEffect(selectedRecordId) { listState.scrollToItem(0) }

    Box(Modifier.fillMaxSize().background(Night)) {
        TrailBackdrop(Modifier.matchParentSize())
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            state = listState,
            contentPadding = PaddingValues(start = 22.dp, top = 19.dp, end = 22.dp, bottom = bottomPadding),
        ) {
            item {
                Row(Modifier.fillMaxWidth().padding(bottom = 28.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).clip(CircleShape)
                        .background(Color(0x442C4964)).border(1.dp, Amber.copy(alpha = .45f), CircleShape)
                        .clickable { if (selectedRecordId == null) onBack() else onSelect(null) },
                        contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.ArrowBack, "返回", tint = Cream)
                    }
                    Spacer(Modifier.width(15.dp))
                    Column {
                        Text("学习足迹", color = Cream, fontSize = 27.sp, fontWeight = FontWeight.Bold)
                        Text("沿着时间，走过每一段学习", color = Mist, fontSize = 12.sp)
                    }
                }
            }
            if (selectedRecordId != null) {
                item {
                    TrailDetail(selectedFocus, selectedClassroom, trustedOrigin, onOpenClassroom)
                }
            } else {
                item {
                    Column(Modifier.fillMaxWidth().padding(bottom = 12.dp)) {
                        Text("TODAY  /  ${today.drop(5).replace('-', '.')} ", color = Amber,
                            fontSize = 11.sp, letterSpacing = 1.6.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(9.dp))
                        Text(if (todayFocusMinutes == 0 && todayClassrooms.isEmpty()) "下一段路，从这里开始"
                            else "课堂 ${if (todayClassSeconds > 0) formatClassroomStudyDuration(todayClassSeconds) else "${todayClassrooms.size} 次"}  ·  专注 $todayFocusMinutes 分钟",
                            color = Cream, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                    }
                }
                if (historyLoading) item { TrailMessage("正在汇总课堂与专注记录…") }
                else if (days.isEmpty()) item { TrailMessage("专注或进入互动课堂后，走过的路会出现在这里。") }
                else items(days, key = { it.first }) { (date, entries) ->
                    TrailDay(date, entries, onSelect)
                }
            }
        }
    }
}

/** A quiet map surface drawn locally, separate from the dashboard illustration and task book. */
@Composable
private fun TrailBackdrop(modifier: Modifier = Modifier) {
    Canvas(modifier) {
        drawRect(Brush.verticalGradient(listOf(Night, Color(0xFF213448), Color(0xFF333444))))
        drawCircle(Brush.radialGradient(listOf(Color(0x44D69E67), Color.Transparent),
            center = Offset(size.width * .86f, size.height * .13f), radius = size.width * .55f),
            radius = size.width * .55f, center = Offset(size.width * .86f, size.height * .13f))
        val contour = Color(0x1EACBCCC)
        for (index in 0..5) {
            val shift = index * size.width * .15f
            val line = Path().apply {
                moveTo(-size.width * .2f + shift, size.height)
                cubicTo(size.width * .72f + shift, size.height * .72f,
                    -size.width * .2f + shift, size.height * .42f,
                    size.width * .83f + shift, -size.height * .08f)
            }
            drawPath(line, contour, style = Stroke(width = 1.dp.toPx()))
        }
        for (row in 0..20) for (column in 0..9) {
            val x = (column + .34f) * size.width / 10f
            val y = (row + .53f) * size.height / 21f
            drawCircle(Color(0x36F6D8A2), .65.dp.toPx(), Offset(x, y))
        }
    }
}

@Composable
private fun TrailMessage(message: String) {
    Text(message, Modifier.fillMaxWidth().padding(top = 38.dp, start = 12.dp), color = Mist,
        fontSize = 14.sp, lineHeight = 22.sp)
}

@Composable
private fun TrailDay(date: String, moments: List<TrailMoment>, onSelect: (String) -> Unit) {
    val parsed = remember(date) { runCatching { LocalDate.parse(date) }.getOrNull() }
    val label = parsed?.let { "${it.monthValue} 月 ${it.dayOfMonth} 日" } ?: "日期未记录"
    val focusMinutes = moments.sumOf { it.focus?.actualMinutes ?: it.briefFocus.sumOf { record -> record.actualMinutes } }
    val classrooms = moments.count { it.classroom != null }
    Column(Modifier.fillMaxWidth().padding(top = 25.dp)) {
        Row(Modifier.fillMaxWidth().padding(start = 9.dp, bottom = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(7.dp).clip(CircleShape).background(Amber))
            Spacer(Modifier.width(13.dp))
            Text(label, color = Cream, fontSize = 19.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            Text("课堂 $classrooms · 专注 $focusMinutes 分", color = Mist, fontSize = 11.sp)
        }
        moments.forEachIndexed { index, moment ->
            Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min)) {
                TrailMarker(moment.classroom != null, index, Modifier.width(45.dp).fillMaxHeight())
                Column(Modifier.weight(1f).padding(bottom = 10.dp)) {
                    when {
                        moment.classroom != null -> ClassroomTicket(moment, onSelect)
                        moment.briefFocus.isNotEmpty() -> BriefTrailMoment(moment, onSelect)
                        moment.focus != null -> FocusTrailMoment(moment.focus, moment.id, onSelect)
                    }
                }
            }
        }
        Text("走过 ${moments.sumOf { if (it.briefFocus.isNotEmpty()) it.briefFocus.size else 1 }} 段学习",
            Modifier.fillMaxWidth().padding(start = 54.dp, top = 4.dp, bottom = 4.dp),
            color = Mist.copy(alpha = .72f), fontSize = 11.sp)
    }
}

@Composable
private fun TrailMarker(classroom: Boolean, index: Int, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val x = size.width * .43f
        val center = Offset(x, 21.dp.toPx())
        val route = Path().apply {
            moveTo(x + if (index % 2 == 0) 3.dp.toPx() else -3.dp.toPx(), 0f)
            cubicTo(x - 11.dp.toPx(), size.height * .32f,
                x + 11.dp.toPx(), size.height * .68f,
                x + if (index % 2 == 0) -3.dp.toPx() else 3.dp.toPx(), size.height)
        }
        drawPath(route, Amber.copy(alpha = .62f), style = Stroke(width = 2.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 5.dp.toPx()))))
        if (classroom) {
            drawCircle(Coral.copy(alpha = .22f), 12.dp.toPx(), center)
            drawCircle(Coral, 5.dp.toPx(), center)
        } else {
            drawOval(Lake, topLeft = Offset(center.x - 5.dp.toPx(), center.y - 6.dp.toPx()),
                size = Size(4.dp.toPx(), 8.dp.toPx()))
            drawOval(Lake, topLeft = Offset(center.x + 2.dp.toPx(), center.y - 1.dp.toPx()),
                size = Size(4.dp.toPx(), 8.dp.toPx()))
        }
    }
}

private val TicketShape = GenericShape { size, _ ->
    val corner = size.width * .035f
    val notch = size.height * .38f
    val radius = size.width * .03f
    moveTo(corner, 0f)
    lineTo(size.width - corner, 0f)
    quadraticBezierTo(size.width, 0f, size.width, corner)
    lineTo(size.width, notch - radius)
    quadraticBezierTo(size.width - radius, notch, size.width, notch + radius)
    lineTo(size.width, size.height - corner)
    quadraticBezierTo(size.width, size.height, size.width - corner, size.height)
    lineTo(corner, size.height)
    quadraticBezierTo(0f, size.height, 0f, size.height - corner)
    lineTo(0f, notch + radius)
    quadraticBezierTo(radius, notch, 0f, notch - radius)
    lineTo(0f, corner)
    quadraticBezierTo(0f, 0f, corner, 0f)
    close()
}

@Composable
private fun ClassroomTicket(moment: TrailMoment, onSelect: (String) -> Unit) {
    val entry = moment.classroom ?: return
    Column(Modifier.fillMaxWidth().clip(TicketShape).background(Cream)
        .border(1.dp, Coral.copy(alpha = .8f), TicketShape)
        .drawBehind {
            val y = size.height * .38f
            drawLine(Coral.copy(alpha = .65f), Offset(7.dp.toPx(), y), Offset(size.width - 7.dp.toPx(), y),
                1.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 4.dp.toPx())))
        }
        .clickable { onSelect(moment.id) }.padding(horizontal = 18.dp, vertical = 13.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${moment.time}  /  课堂", color = Color(0xFF99634B), fontSize = 11.sp,
                letterSpacing = .6.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            Text("CAMPUS", color = Color(0xFF99634B), fontSize = 10.sp, letterSpacing = 1.sp)
        }
        Spacer(Modifier.height(19.dp))
        Text(entry.courseName, color = Night, fontSize = 17.sp, fontWeight = FontWeight.Bold,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text(if (entry.visits.isEmpty()) "到访记录待补充" else "累计 ${formatClassroomStudyDuration(entry.visits.sumOf { it.activeSeconds })}",
            color = Color(0xFF6E7580), fontSize = 12.sp)
    }
}

@Composable
private fun FocusTrailMoment(record: FocusRecord, id: String, onSelect: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { onSelect(id) }.padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("${FocusMode.byName(record.mode).label} · ${if (record.actualMinutes > 0) "${record.actualMinutes} 分钟" else "不足 1 分钟"}",
                color = Cream, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            Text(record.endedAt.take(5), color = Mist, fontSize = 11.sp)
        }
        Icon(Icons.Default.ChevronRight, "查看本次学习", Modifier.size(19.dp), tint = Amber)
    }
}

@Composable
private fun BriefTrailMoment(moment: TrailMoment, onSelect: (String) -> Unit) {
    var expanded by rememberSaveable(moment.id) { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().clickable { expanded = !expanded }.padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("短时专注 · ${moment.briefFocus.size} 次", color = Cream,
                fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            Text("${moment.briefFocus.last().endedAt.take(5)}–${moment.briefFocus.first().endedAt.take(5)}",
                color = Mist, fontSize = 11.sp)
        }
        Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
            if (expanded) "收起记录" else "展开记录", Modifier.size(19.dp), tint = Amber)
    }
    if (expanded) moment.briefFocus.forEach { record ->
        FocusTrailMoment(record, "focus:${record.sourceId}", onSelect)
    }
}

@Composable
private fun TrailDetail(
    focus: FocusRecord?, classroom: ClassroomFootprint?, trustedOrigin: String?, onOpenClassroom: (String) -> Unit,
) {
    Column(Modifier.fillMaxWidth().drawBehind {
        val x = 10.dp.toPx()
        val path = Path().apply {
            moveTo(x, 0f)
            cubicTo(x - 8.dp.toPx(), size.height * .3f,
                x + 8.dp.toPx(), size.height * .7f, x, size.height)
        }
        drawPath(path, Amber.copy(alpha = .6f), style = Stroke(width = 2.dp.toPx(),
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6.dp.toPx(), 5.dp.toPx()))))
        drawCircle(Coral, 5.dp.toPx(), Offset(x, 17.dp.toPx()))
    }.padding(start = 34.dp, end = 6.dp)) {
        Text("ROUTE  /  STUDY RECORD", color = Amber, fontSize = 11.sp,
            letterSpacing = 1.5.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(16.dp))
        when {
            classroom != null -> {
                Text(classroom.courseName, color = Cream, fontSize = 26.sp, fontWeight = FontWeight.Bold,
                    lineHeight = 33.sp)
                Text("互动课堂 · ${(classroom.enteredAt ?: classroom.item.createdAt).classroomTimeLabel()}",
                    Modifier.padding(top = 8.dp), color = Mist, fontSize = 13.sp)
                val totalSeconds = classroom.visits.sumOf { it.activeSeconds }
                if (classroom.visits.isNotEmpty()) {
                    TrailDetailMetric("累计学习", formatClassroomStudyDuration(totalSeconds))
                    Text("到访记录", Modifier.padding(top = 25.dp, bottom = 8.dp),
                        color = Amber, fontSize = 13.sp, fontWeight = FontWeight.Bold)
                    classroom.visits.sortedByDescending { it.enteredAt }.forEach { visit ->
                        Text("${visit.enteredAt.classroomTimeLabel()}  ·  ${formatClassroomStudyDuration(visit.activeSeconds)}  ·  ${if (visit.completed) "已结束" else "暂时离开"}",
                            Modifier.fillMaxWidth().padding(vertical = 9.dp), color = Cream, fontSize = 12.sp)
                    }
                }
                val safe = ClassroomUrlPolicy.sanitize(classroom.item.url, listOf(trustedOrigin),
                    allowEmulatorDebug = BuildConfig.DEBUG)
                if (safe != null) {
                    Spacer(Modifier.height(22.dp))
                    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(5.dp)).background(Amber)
                        .clickable { onOpenClassroom(safe) }.padding(vertical = 15.dp),
                        contentAlignment = Alignment.Center) {
                        Text("继续上课  →", color = Night, fontSize = 15.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
            focus != null -> {
                Text(if (focus.actualMinutes > 0) "专注了 ${focus.actualMinutes} 分钟" else "一次短时专注",
                    color = Cream, fontSize = 26.sp, fontWeight = FontWeight.Bold)
                Text("${focus.date}  ·  ${focus.endedAt}", Modifier.padding(top = 8.dp), color = Mist, fontSize = 13.sp)
                focus.goal?.takeIf { it.isNotBlank() }?.let {
                    TrailDetailMetric("本次目标", it)
                }
                TrailDetailMetric("我的学习收获", focus.selfReport?.takeIf { it.isNotBlank() } ?: "这次没有填写学习收获。")
            }
            else -> Text("这条记录暂时无法加载，请返回列表重试。", color = Cream)
        }
    }
}

@Composable
private fun TrailDetailMetric(label: String, value: String) {
    Column(Modifier.fillMaxWidth().padding(top = 26.dp)
        .drawBehind { drawLine(Amber.copy(alpha = .4f), Offset.Zero, Offset(size.width, 0f), 1.dp.toPx()) }
        .padding(top = 17.dp)) {
        Text(label, color = Amber, fontSize = 12.sp, fontWeight = FontWeight.Bold)
        Text(value, Modifier.padding(top = 6.dp), color = Cream, fontSize = 16.sp, lineHeight = 25.sp)
    }
}

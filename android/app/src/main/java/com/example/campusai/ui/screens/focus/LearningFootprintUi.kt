package com.example.campusai.ui.screens.focus

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Timer
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.BuildConfig
import com.example.campusai.data.model.FocusMode
import com.example.campusai.data.model.FocusRecord
import com.example.campusai.data.remote.ClassroomUrlPolicy
import com.example.campusai.ui.screens.courses.formatClassroomStudyDuration
import java.time.LocalDate
import java.time.ZoneId

private val FootprintInk = Color(0xFF263B50)
private val FootprintMuted = Color(0xFF66727A)
private val FootprintClay = Color(0xFFAA684D)
private val FootprintBlue = Color(0xFF6D8B9B)
private val FootprintPaper = Color(0xFFF9F2E3)
private val FootprintGold = Color(0xFFC3955B)

private data class FootprintMoment(
    val id: String,
    val date: String,
    val clock: String,
    val classroom: ClassroomFootprint? = null,
    val record: FocusRecord? = null,
    val briefRecords: List<FocusRecord> = emptyList(),
)

private fun classroomMoment(entry: ClassroomFootprint): FootprintMoment {
    val stamp = (entry.enteredAt ?: entry.item.createdAt).classroomTimeLabel()
    return FootprintMoment(
        id = "classroom:${entry.item.sessionId ?: entry.item.url}",
        date = stamp.take(10).takeIf { it.matches(Regex("\\d{4}-\\d{2}-\\d{2}")) } ?: "0000-00-00",
        clock = stamp.drop(11).take(5),
        classroom = entry,
    )
}

/** Keep the two sources in one chronology; only consecutive short sessions are folded together. */
private fun footprintMoments(records: List<FocusRecord>, classrooms: List<ClassroomFootprint>): List<FootprintMoment> {
    val sorted = (classrooms.map(::classroomMoment) + records.map {
        FootprintMoment("focus:${it.sourceId}", it.date, it.endedAt.take(5), record = it)
    }).sortedWith(compareByDescending<FootprintMoment> { it.date }.thenByDescending { it.clock })
    val result = mutableListOf<FootprintMoment>()
    var cursor = 0
    while (cursor < sorted.size) {
        val first = sorted[cursor]
        if (first.record?.let { it.actualMinutes == 0 && it.mode == FocusMode.FOCUS.name } == true) {
            var end = cursor + 1
            while (end < sorted.size && sorted[end].date == first.date &&
                sorted[end].record?.let { it.actualMinutes == 0 && it.mode == FocusMode.FOCUS.name } == true) end++
            if (end - cursor > 1) {
                result += first.copy(id = "brief:${first.date}:${first.id}", record = null,
                    briefRecords = sorted.subList(cursor, end).mapNotNull { it.record })
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
    val moments = remember(records, classrooms) { footprintMoments(records, classrooms) }
    val selectedRecord = records.firstOrNull { "focus:${it.sourceId}" == selectedRecordId }
    val selectedClassroom = classrooms.firstOrNull { "classroom:${it.item.sessionId ?: it.item.url}" == selectedRecordId }
    val today = remember { LocalDate.now(ZoneId.systemDefault()).toString() }
    val todayRecords = records.filter { it.date == today }
    val todayClassroomEntries = classrooms.filter { classroomMoment(it).date == today }
    val todayClassroomSeconds = todayClassroomEntries.sumOf { entry -> entry.visits.sumOf { it.activeSeconds } }
    val bottomPadding = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 24.dp
    val listState = rememberLazyListState()
    LaunchedEffect(selectedRecordId) { listState.scrollToItem(0) }

    androidx.compose.foundation.layout.Box(Modifier.fillMaxSize()) {
        Image(painterResource(R.drawable.campus_twilight_original), null,
            Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        androidx.compose.foundation.layout.Box(Modifier.fillMaxSize().background(Color(0xA9182747)))
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            state = listState,
            contentPadding = PaddingValues(start = 20.dp, top = 18.dp, end = 20.dp, bottom = bottomPadding),
            verticalArrangement = Arrangement.spacedBy(0.dp),
        ) {
            item {
                Row(Modifier.fillMaxWidth().padding(bottom = 20.dp), verticalAlignment = Alignment.CenterVertically) {
                    androidx.compose.foundation.layout.Box(
                        Modifier.size(48.dp).clip(CircleShape).background(Color(0xE5F6F0E6))
                            .clickable { if (selectedRecordId != null) onSelect(null) else onBack() },
                        contentAlignment = Alignment.Center,
                    ) { Icon(Icons.Default.ArrowBack, "返回", tint = FootprintInk) }
                    Spacer(Modifier.width(13.dp))
                    Column {
                        Text(if (selectedRecordId == null) "学习足迹" else "足迹档案", color = Color.White,
                            fontSize = 28.sp, fontWeight = FontWeight.Bold)
                        Text(if (selectedRecordId == null) "沿着时间，拾起今天的学习" else "这一程，已经留在记录里",
                            color = Color(0xFFFFE8C9), fontSize = 12.sp)
                    }
                }
            }
            if (selectedRecordId != null) {
                item {
                    FootprintPage {
                        Text("CAMPUS  /  LEARNING FOOTPRINT", color = FootprintClay,
                            fontSize = 11.sp, letterSpacing = 1.3.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.height(18.dp))
                        when {
                            selectedClassroom != null -> ClassroomFootprintDetail(selectedClassroom, trustedOrigin, onOpenClassroom)
                            selectedRecord != null -> FocusFootprintDetail(selectedRecord)
                            else -> Text("这条记录暂时无法加载，请返回列表重试。", color = FootprintInk)
                        }
                    }
                }
            } else {
                item {
                    FootprintPage {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text("CAMPUS  /  FIELD NOTES", color = FootprintClay, fontSize = 11.sp,
                                    letterSpacing = 1.2.sp, fontWeight = FontWeight.Bold)
                                Spacer(Modifier.height(12.dp))
                                Text("今日足迹", color = FootprintInk, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                                Text(if (todayRecords.isEmpty() && todayClassroomEntries.isEmpty()) "下一段学习，从这里开始"
                                    else "课堂 ${if (todayClassroomSeconds > 0) formatClassroomStudyDuration(todayClassroomSeconds) else "${todayClassroomEntries.size} 次"}  ·  专注 ${todayRecords.sumOf { it.actualMinutes }} 分钟",
                                    color = FootprintMuted, fontSize = 13.sp)
                            }
                            Text(LocalDate.now().format(java.time.format.DateTimeFormatter.ofPattern("MM / dd")),
                                color = FootprintClay, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                        }
                        Spacer(Modifier.height(18.dp))
                        androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().height(1.dp).background(FootprintGold.copy(alpha = .55f)))
                        if (historyLoading) {
                            Text("正在汇总课堂与专注记录…", Modifier.padding(vertical = 28.dp), color = FootprintMuted)
                        } else if (moments.isEmpty()) {
                            Text("专注或进入互动课堂后，足迹会出现在这里。",
                                Modifier.padding(vertical = 28.dp), color = FootprintMuted)
                        } else {
                            moments.groupBy { it.date }.forEach { (date, dayMoments) ->
                                FootprintDay(date, dayMoments, onSelect)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun FootprintPage(content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(topStart = 4.dp, topEnd = 24.dp, bottomStart = 4.dp, bottomEnd = 6.dp)
    Column(
        Modifier.fillMaxWidth().clip(shape)
            .background(Brush.horizontalGradient(listOf(Color(0xFFD7C5A8), FootprintPaper, Color(0xFFFFFAED))))
            .drawBehind {
                drawLine(Color(0x888D785C), Offset(12.dp.toPx(), 0f), Offset(12.dp.toPx(), size.height), 1.dp.toPx())
                for (line in 0..(size.height / 26.dp.toPx()).toInt()) {
                    val y = line * 26.dp.toPx()
                    drawLine(Color(0x12A07953), Offset(20.dp.toPx(), y), Offset(size.width, y), .6.dp.toPx())
                }
            }
            .border(1.dp, Color(0x99D0B998), shape)
            .padding(start = 31.dp, end = 22.dp, top = 27.dp, bottom = 32.dp),
        content = content,
    )
}

@Composable
private fun FootprintDay(date: String, moments: List<FootprintMoment>, onSelect: (String) -> Unit) {
    val parsed = remember(date) { runCatching { LocalDate.parse(date) }.getOrNull() }
    val label = parsed?.let { "${it.monthValue} 月 ${it.dayOfMonth} 日" } ?: "日期未记录"
    val focusMinutes = moments.sumOf { it.record?.actualMinutes ?: it.briefRecords.sumOf { record -> record.actualMinutes } }
    val classroomCount = moments.count { it.classroom != null }
    Column(Modifier.fillMaxWidth().padding(top = 24.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, color = FootprintInk, fontSize = 19.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            Text("课堂 $classroomCount · 专注 $focusMinutes 分", color = FootprintMuted, fontSize = 11.sp)
        }
        Spacer(Modifier.height(13.dp))
        moments.forEach { moment ->
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
                Column(Modifier.width(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    androidx.compose.foundation.layout.Box(Modifier.padding(top = 16.dp).size(9.dp)
                        .clip(CircleShape).background(if (moment.classroom != null) FootprintClay else FootprintBlue))
                    androidx.compose.foundation.layout.Box(Modifier.width(1.dp).height(if (moment.classroom != null) 101.dp else 59.dp)
                        .background(FootprintBlue.copy(alpha = .45f)))
                }
                Column(Modifier.weight(1f).padding(bottom = 10.dp)) {
                    if (moment.classroom != null) ClassroomTicket(moment, onSelect)
                    else if (moment.briefRecords.isNotEmpty()) BriefFootprints(moment, onSelect)
                    else moment.record?.let { FocusFootprintRow(it, moment.id, onSelect) }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            androidx.compose.foundation.layout.Box(Modifier.weight(1f).height(1.dp).background(FootprintGold.copy(alpha = .5f)))
            Text(" $date  ·  已收藏 ",
                Modifier.graphicsLayer { rotationZ = -3f }
                    .border(1.dp, FootprintClay.copy(alpha = .6f), RoundedCornerShape(3.dp))
                    .padding(horizontal = 5.dp, vertical = 4.dp),
                color = FootprintClay, fontSize = 10.sp,
                letterSpacing = 1.sp, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun ClassroomTicket(moment: FootprintMoment, onSelect: (String) -> Unit) {
    val entry = moment.classroom ?: return
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(3.dp)).background(Color(0x9FFFF9ED))
            .border(1.dp, FootprintClay.copy(alpha = .55f), RoundedCornerShape(3.dp))
            .clickable { onSelect(moment.id) }.padding(13.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.MenuBook, null, Modifier.size(17.dp), tint = FootprintClay)
            Spacer(Modifier.width(6.dp))
            Text("课堂入场券", color = FootprintClay, fontSize = 11.sp, letterSpacing = 1.sp)
            Spacer(Modifier.weight(1f))
            Text(moment.clock, color = FootprintMuted, fontSize = 11.sp)
        }
        Spacer(Modifier.height(8.dp))
        Text(entry.courseName, color = FootprintInk, fontSize = 16.sp, fontWeight = FontWeight.Bold,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
        Text(if (entry.visits.isEmpty()) "进入记录待补充" else "累计 ${formatClassroomStudyDuration(entry.visits.sumOf { it.activeSeconds })}",
            color = FootprintMuted, fontSize = 12.sp)
    }
}

@Composable
private fun FocusFootprintRow(record: FocusRecord, id: String, onSelect: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable { onSelect(id) }.padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Timer, null, Modifier.size(18.dp), tint = FootprintBlue)
        Spacer(Modifier.width(9.dp))
        Column(Modifier.weight(1f)) {
            Text("${FocusMode.byName(record.mode).label} · ${if (record.actualMinutes > 0) "${record.actualMinutes} 分钟" else "不足 1 分钟"}",
                color = FootprintInk, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            Text(record.endedAt.take(5), color = FootprintMuted, fontSize = 11.sp)
        }
        Icon(Icons.Default.ChevronRight, "查看本次学习", Modifier.size(19.dp), tint = FootprintBlue)
    }
}

@Composable
private fun BriefFootprints(moment: FootprintMoment, onSelect: (String) -> Unit) {
    var expanded by rememberSaveable(moment.id) { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().clickable { expanded = !expanded }.padding(vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Default.Timer, null, Modifier.size(18.dp), tint = FootprintBlue)
        Spacer(Modifier.width(9.dp))
        Column(Modifier.weight(1f)) {
            Text("短时专注 · ${moment.briefRecords.size} 次", color = FootprintInk,
                fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
            Text("${moment.briefRecords.last().endedAt.take(5)}–${moment.briefRecords.first().endedAt.take(5)}",
                color = FootprintMuted, fontSize = 11.sp)
        }
        Icon(if (expanded) Icons.Default.ExpandLess else Icons.Default.ExpandMore,
            if (expanded) "收起记录" else "展开记录", Modifier.size(19.dp), tint = FootprintBlue)
    }
    if (expanded) moment.briefRecords.forEach { record ->
        FocusFootprintRow(record, "focus:${record.sourceId}", onSelect)
    }
}

@Composable
private fun ClassroomFootprintDetail(entry: ClassroomFootprint, trustedOrigin: String?, onOpenClassroom: (String) -> Unit) {
    Text("互动课堂", color = FootprintClay, fontSize = 12.sp, fontWeight = FontWeight.Bold)
    Text(entry.courseName, color = FootprintInk, fontSize = 24.sp, fontWeight = FontWeight.Bold)
    Spacer(Modifier.height(12.dp))
    Text("${if (entry.enteredAt != null) "进入" else "创建"}于 ${(entry.enteredAt ?: entry.item.createdAt).classroomTimeLabel()}",
        color = FootprintMuted, fontSize = 13.sp)
    if (entry.visits.isNotEmpty()) {
        Text("累计学习 ${formatClassroomStudyDuration(entry.visits.sumOf { it.activeSeconds })}",
            color = FootprintInk, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(22.dp))
        Text("到访记录", color = FootprintClay, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        entry.visits.sortedByDescending { it.enteredAt }.forEach { visit ->
            Text("${visit.enteredAt.classroomTimeLabel()}  ·  ${formatClassroomStudyDuration(visit.activeSeconds)}  ·  ${if (visit.completed) "已结束" else "暂时离开"}",
                Modifier.padding(top = 9.dp), color = FootprintInk, fontSize = 12.sp)
        }
    }
    val safe = ClassroomUrlPolicy.sanitize(entry.item.url, listOf(trustedOrigin), allowEmulatorDebug = BuildConfig.DEBUG)
    if (safe != null) {
        Spacer(Modifier.height(26.dp))
        Text("继续上课  →", Modifier.clickable { onOpenClassroom(safe) }.padding(vertical = 10.dp),
            color = FootprintClay, fontSize = 15.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun FocusFootprintDetail(record: FocusRecord) {
    Text(record.date + "  /  " + record.endedAt, color = FootprintClay, fontSize = 12.sp)
    Text(if (record.actualMinutes > 0) "专注了 ${record.actualMinutes} 分钟" else "一次短时专注",
        color = FootprintInk, fontSize = 24.sp, fontWeight = FontWeight.Bold)
    Spacer(Modifier.height(19.dp))
    record.goal?.takeIf { it.isNotBlank() }?.let {
        Text("本次目标", color = FootprintClay, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        Text(it, Modifier.padding(top = 6.dp), color = FootprintInk, fontSize = 15.sp, lineHeight = 23.sp)
        Spacer(Modifier.height(20.dp))
    }
    Text("我的学习收获", color = FootprintClay, fontSize = 13.sp, fontWeight = FontWeight.Bold)
    Text(record.selfReport?.takeIf { it.isNotBlank() } ?: "这次没有填写学习收获。",
        Modifier.padding(top = 7.dp), color = FootprintInk, fontSize = 15.sp, lineHeight = 23.sp)
}

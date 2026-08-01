package com.example.campusai.ui.screens.classrooms

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material3.Icon
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.ClassroomAvailability
import com.example.campusai.data.model.ClassroomQuery
import com.example.campusai.data.repository.ClassroomRepository
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch
import java.time.format.DateTimeFormatter

@Composable
fun ClassroomsScreen(repository: ClassroomRepository, reduceMotion: Boolean, onBack: () -> Unit) {
    val loading by repository.loading.collectAsState()
    val slots = remember { repository.slots() }
    val dates = remember { repository.availableDates(System.currentTimeMillis()).map { it.format(DateTimeFormatter.ofPattern("M月d日")) to it.toString() } }
    val scope = rememberCoroutineScope()
    var campus by remember { mutableStateOf<String?>(null) }
    var building by remember { mutableStateOf<String?>(null) }
    var date by remember { mutableStateOf<String?>(null) }
    var selectedSlot by remember { mutableStateOf(1) }
    var capacity by remember { mutableStateOf("全部容量") }
    var multimedia by remember { mutableStateOf(true) }
    var hint by remember { mutableStateOf<String?>(null) }
    var results by remember { mutableStateOf<List<ClassroomAvailability>>(emptyList()) }
    LaunchedEffect(Unit) { results = repository.query(ClassroomQuery(repository.campuses().first(), repository.buildings(repository.campuses().first()).first(), dates.first().second, setOf(1), 0, true)) }
    fun query() {
        if (campus == null || building == null || date == null) { hint = "请选择校区、教学楼和日期后再查询"; return }
        hint = null; scope.launch { results = repository.query(ClassroomQuery(campus, building, date, setOf(selectedSlot), when (capacity) { ">=40座" -> 40; ">=80座" -> 80; ">=100座" -> 100; else -> 0 }, multimedia)) }
    }
    LazyColumn(Modifier.fillMaxWidth().background(Background), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = BottomDockReservedHeight + 18.dp), verticalArrangement = Arrangement.spacedBy(15.dp)) {
        item { ClassroomHero(onBack) }
        item {
            Column(Modifier.clip(RoundedCornerShape(25.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(25.dp)).padding(16.dp).enterAnimation(enabled = !reduceMotion)) {
                FilterField(Icons.Default.Apartment, "校区") { FormDropdown(repository.campuses(), campus, { campus = it; building = null }, "选择校区") }
                Spacer(Modifier.height(12.dp)); FilterField(Icons.Default.MeetingRoom, "教学楼") { FormDropdown(campus?.let(repository::buildings).orEmpty(), building, { building = it }, "请选择教学楼") }
                Spacer(Modifier.height(12.dp)); FilterField(Icons.Default.CalendarMonth, "日期") { FormDropdown(dates.map { it.first }, dates.firstOrNull { it.second == date }?.first, { picked -> date = dates.first { it.first == picked }.second }, "请选择日期") }
                Spacer(Modifier.height(16.dp)); FilterPanel(slots.map { it.index to it.label }, selectedSlot, { selectedSlot = it }, capacity, { capacity = it }, multimedia, { multimedia = it })
                hint?.let { Text(it, color = Color(0xFFE35F42), fontSize = 11.sp, modifier = Modifier.padding(top = 10.dp)) }
                Spacer(Modifier.height(16.dp)); Box(Modifier.fillMaxWidth().height(55.dp).clip(CircleShape).background(Primary).campusClickable { query() }, contentAlignment = Alignment.Center) { Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Search, null, tint = Color.White); Spacer(Modifier.width(8.dp)); Text(if (loading) "正在查询..." else "查询空闲教室", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold) } }
            }
        }
        item { Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(width = 5.dp, height = 25.dp).clip(CircleShape).background(Primary)); Spacer(Modifier.width(9.dp)); Text("推荐空教室", color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.width(12.dp)); Text("根据你的筛选条件为你推荐", color = Muted, fontSize = 10.5.sp, modifier = Modifier.weight(1f)); Text("共 ${results.size} 间可用  ›", color = Muted, fontSize = 11.sp) } }
        if (results.isEmpty() && !loading) item { Text("当前条件下没有可用教室，请调整筛选条件。", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(vertical = 24.dp) ) }
        items(results, key = { it.classroom.id }) { ClassroomCard(it) }
    }
}

@Composable private fun ClassroomHero(onBack: () -> Unit) { Box(Modifier.fillMaxWidth().height(220.dp)) { Image(painterResource(R.drawable.hero_classroom), null, Modifier.fillMaxWidth().height(220.dp), contentScale = ContentScale.Crop, alpha = .82f); Row(Modifier.padding(top = 34.dp), verticalAlignment = Alignment.CenterVertically) { RoundBack(onBack); Spacer(Modifier.width(16.dp)); Column { Text("空教室查询", color = TextPrimary, fontSize = 30.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(8.dp)); Text("基于课程占用数据，帮你快速找到可用教室", color = Muted, fontSize = 14.sp) } } } }
@Composable private fun RoundBack(onBack: () -> Unit) { Box(Modifier.size(48.dp).clip(CircleShape).background(Surface).border(1.dp, Line, CircleShape).campusClickable { onBack() }, contentAlignment = Alignment.Center) { Icon(Icons.Default.ChevronRight, "返回", tint = TextPrimary, modifier = Modifier.size(28.dp).rotate(180f)) } }
@Composable private fun FilterField(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, content: @Composable () -> Unit) { Row(verticalAlignment = Alignment.CenterVertically) { Box(Modifier.size(44.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) { Icon(icon, null, tint = Primary, modifier = Modifier.size(22.dp)) }; Spacer(Modifier.width(10.dp)); Text(label, color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.width(85.dp)); Box(Modifier.weight(1f)) { content() } } }
@Composable private fun FilterPanel(slots: List<Pair<Int, String>>, selectedSlot: Int, onSlot: (Int) -> Unit, capacity: String, onCapacity: (String) -> Unit, multimedia: Boolean, onMultimedia: (Boolean) -> Unit) { Column(Modifier.clip(RoundedCornerShape(18.dp)).border(1.dp, Line, RoundedCornerShape(18.dp)).padding(14.dp)) { Text("◷  节次", color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(12.dp)); ChipRow(slots.map { it.second }, slots.first { it.first == selectedSlot }.second) { label -> onSlot(slots.first { it.second == label }.first) }; Spacer(Modifier.height(16.dp)); Box(Modifier.fillMaxWidth().height(1.dp).background(Line)); Spacer(Modifier.height(14.dp)); Text("♟  容量", color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(12.dp)); ChipRow(listOf("全部容量", ">=40座", ">=80座", ">=100座"), capacity, onCapacity); Spacer(Modifier.height(16.dp)); Box(Modifier.fillMaxWidth().height(1.dp).background(Line)); Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Tv, null, tint = Primary); Spacer(Modifier.width(10.dp)); Column(Modifier.weight(1f)) { Text("仅显示有多媒体设备", color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold); Text("投影、音响等教学设备", color = Muted, fontSize = 10.5.sp) }; Switch(multimedia, onMultimedia, colors = SwitchDefaults.colors(checkedTrackColor = Primary, checkedThumbColor = Surface, uncheckedTrackColor = PrimarySoft)) } } }
@Composable private fun ChipRow(options: List<String>, selected: String, onClick: (String) -> Unit) { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) { options.forEach { item -> Box(Modifier.weight(1f).clip(CircleShape).background(if (item == selected) Primary else Surface).border(1.dp, if (item == selected) Primary else Line, CircleShape).campusClickable { onClick(item) }.padding(vertical = 8.dp), contentAlignment = Alignment.Center) { Text(item, color = if (item == selected) Color.White else Muted, fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, maxLines = 1) } } } }
@Composable private fun ClassroomCard(item: ClassroomAvailability) { Column(Modifier.clip(RoundedCornerShape(18.dp)).background(Surface).padding(12.dp)) { Row(verticalAlignment = Alignment.CenterVertically) { Image(painterResource(R.drawable.hero_classroom), null, Modifier.size(width = 112.dp, height = 82.dp).clip(RoundedCornerShape(12.dp)), contentScale = ContentScale.Crop); Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) { Text(item.classroom.name, color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(7.dp)); Row { Icon(Icons.Default.Apartment, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" ${item.classroom.building}", color = Muted, fontSize = 11.sp); Spacer(Modifier.width(13.dp)); Icon(Icons.Default.People, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" ${item.classroom.capacity} 座", color = Muted, fontSize = 11.sp) }; Spacer(Modifier.height(8.dp)); Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) { SmallTag(item.freeSlots.firstOrNull()?.label ?: "可用", PrimarySoft, Primary); if (item.classroom.hasMultimedia) SmallTag("投影仪", Color(0xFFEAF9F3), Success); SmallTag("音响", Color(0xFFEAF9F3), Success) } }; SmallTag("✓ 可用", Color(0xFFEAF9F3), Success) } } }
@Composable private fun SmallTag(text: String, bg: Color, fg: Color) { Text(text, color = fg, fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.clip(CircleShape).background(bg).padding(horizontal = 8.dp, vertical = 5.dp)) }

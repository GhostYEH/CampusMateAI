package com.example.campusai.ui.screens.courses

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.R
import com.example.campusai.data.model.Course
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.ApiFocusRepository
import kotlinx.coroutines.launch
import java.time.LocalDate

private val libraryCream = Color(0xFFF5F2E8)
private val libraryGreen = Color(0xFF214E3D)
private val bookColors = listOf(
    Color(0xFF325F5A), Color(0xFF994D3D), Color(0xFF3B527C),
    Color(0xFF8B6A3D), Color(0xFF5B526F), Color(0xFF3F654A),
)

/** The campus library only shows courses confirmed to come from the student's account. */
@Composable
fun LibraryScreen(
    repository: AppRepository,
    focusRepository: ApiFocusRepository,
    initialCourseId: String? = null,
    initialSessionId: String? = null,
    onBack: () -> Unit,
    onConnectChaoxing: () -> Unit,
    onOpenCounselor: (String, String, String) -> Unit,
    onStartFocus: (String) -> Unit,
) {
    val courses by repository.courses.collectAsStateWithLifecycle()
    val focusRecords by focusRepository.records.collectAsStateWithLifecycle()
    val realCourses = courses.filter { it.provider.equals("chaoxing", ignoreCase = true) }
    val today = LocalDate.now()
    val termStart = currentTermStart(today)
    val termEnd = termStart.plusMonths(6).minusDays(1)
    val currentCourses = realCourses.filter { it.isInTerm(termStart, termEnd) }
        .sortedWith(compareByDescending<Course> { it.startDate() != null }.thenByDescending { it.startDate() }.thenBy { it.name })
    val otherCourses = realCourses.filterNot { it.isInTerm(termStart, termEnd) }
        .sortedWith(compareByDescending<Course> { it.startDate() != null }.thenByDescending { it.startDate() }.thenBy { it.name })
    val scope = rememberCoroutineScope()
    var accountStatus by remember { mutableStateOf("checking") }
    var lastSyncedAt by remember { mutableStateOf<String?>(null) }
    var syncing by remember { mutableStateOf(false) }
    var syncMessage by remember { mutableStateOf<String?>(null) }
    var selectedCourse by remember { mutableStateOf<Course?>(null) }
    var statusRefreshToken by remember { mutableIntStateOf(0) }

    LaunchedEffect(statusRefreshToken) {
        val status = repository.getChaoxingStatus()
        accountStatus = status?.status ?: "unavailable"
        lastSyncedAt = status?.last_synced_at
        repository.refreshCourses()
        focusRepository.refreshHistoryAndGoal()
    }
    LaunchedEffect(realCourses, initialCourseId) {
        if (selectedCourse == null && !initialCourseId.isNullOrBlank()) {
            selectedCourse = realCourses.firstOrNull { it.id == initialCourseId }
        }
    }

    Box(Modifier.fillMaxSize()) {
        Image(
            painter = painterResource(R.drawable.focus_scene_quiet_library),
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop,
        )
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xC9152536), Color(0x90152536), Color(0xDB0C1A25)))))
        LazyColumn(
            modifier = Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding(),
            contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 18.dp, bottom = 36.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(44.dp).clip(CircleShape)
                            .background(Color.White.copy(alpha = .18f)).clickable(onClick = onBack),
                        contentAlignment = Alignment.Center,
                    ) { Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color.White) }
                    Column(Modifier.padding(start = 14.dp)) {
                        Text("图书馆", color = Color.White, fontSize = 25.sp, fontWeight = FontWeight.Bold)
                        Text("从你的课程出发，找到今天要学的内容", color = Color.White.copy(alpha = .82f), fontSize = 12.sp)
                    }
                }
            }
            item {
                Column(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp))
                        .background(libraryCream.copy(alpha = .95f)).padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Icon(Icons.Default.MenuBook, contentDescription = null, tint = libraryGreen)
                        Column {
                            Text("我的课程书架", color = libraryGreen, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                            Text(
                                when (accountStatus) {
                                    "online" -> "已连接学习通 · ${realCourses.size} 门课程"
                                    "expired" -> "学习通登录已失效，请重新连接"
                                    "offline" -> "连接学习通后，课程会摆上书架"
                                    "checking" -> "正在检查学习通连接…"
                                    else -> "暂时无法确认连接，请检查网络"
                                }, color = Color(0xFF596B61), fontSize = 12.sp,
                            )
                        }
                    }
                    if (accountStatus == "online") {
                        lastSyncedAt?.let { Text("上次同步：${it.take(16).replace('T', ' ')}", color = Color(0xFF64756B), fontSize = 11.sp) }
                        LibraryAction("同步课程", onClick = {
                            if (!syncing) scope.launch {
                                syncing = true
                                val result = repository.syncChaoxing()
                                if (result.first) {
                                    repository.refreshCourses()
                                    lastSyncedAt = repository.getChaoxingStatus()?.last_synced_at
                                    syncMessage = "课程已更新"
                                } else {
                                    syncMessage = if (result.second == "reauth_required" || result.second == "verification_required") {
                                        accountStatus = "expired"
                                        "登录已失效，请重新连接"
                                    } else "同步失败：${result.second}"
                                }
                                syncing = false
                            }
                        }, busy = syncing)
                    } else if (accountStatus == "offline" || accountStatus == "expired") {
                        LibraryAction(if (accountStatus == "expired") "重新连接学习通" else "连接学习通", onConnectChaoxing)
                    } else if (accountStatus == "unavailable") {
                        LibraryAction("重试连接", onClick = { statusRefreshToken++ })
                    }
                    syncMessage?.let { Text(it, color = libraryGreen, fontSize = 12.sp) }
                }
            }
            if (accountStatus == "online") {
                if (realCourses.isEmpty()) {
                    item {
                        LibraryNote("还没有同步到课程", "同步后会展示学习通返回的课程；这里不会填入演示课程。")
                    }
                } else {
                    if (currentCourses.isNotEmpty()) {
                        item { ShelfHeading("本学期", "最近开课的课程放在前面", currentCourses.size) }
                        itemsIndexed(currentCourses.chunked(3)) { row, shelf ->
                            CourseShelfRow(shelf, row) { selectedCourse = it }
                        }
                    }
                    if (otherCourses.isNotEmpty()) {
                        item { ShelfHeading("其他课程", "按开课时间从新到旧", otherCourses.size) }
                        itemsIndexed(otherCourses.chunked(3)) { row, shelf ->
                            CourseShelfRow(shelf, row + currentCourses.size) { selectedCourse = it }
                        }
                    }
                }
            }
            item { Text("轻触书脊打开课程", color = Color.White.copy(alpha = .72f), fontSize = 12.sp) }
        }
    }
    selectedCourse?.let { course ->
        CourseDetailSheet(
            course = course,
            repository = repository,
            initialSessionId = initialSessionId,
            onDismiss = { selectedCourse = null },
            onOpenCounselor = onOpenCounselor,
            onStartFocus = onStartFocus,
            courseRecords = focusRecords.filter { it.goal?.contains("《${course.name}》") == true },
        )
    }
}

private fun currentTermStart(today: LocalDate): LocalDate = when (today.monthValue) {
    1, 2 -> LocalDate.of(today.year - 1, 9, 1)
    in 3..8 -> LocalDate.of(today.year, 3, 1)
    else -> LocalDate.of(today.year, 9, 1)
}

private fun Course.startDate(): LocalDate? = startsAt?.take(10)?.let { raw ->
    runCatching { LocalDate.parse(raw) }.getOrNull()
}

private fun Course.isInTerm(start: LocalDate, end: LocalDate): Boolean {
    if (semester?.contains("本学期") == true) return true
    val date = startDate() ?: return false
    return !date.isBefore(start) && !date.isAfter(end)
}

@Composable
private fun ShelfHeading(title: String, subtitle: String, count: Int) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Bottom) {
        Column {
            Text(title, color = Color.White, fontSize = 21.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Color.White.copy(alpha = .68f), fontSize = 11.sp)
        }
        Text("$count 本", color = Color(0xFFEBD5A8), fontSize = 12.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun CourseShelfRow(courses: List<Course>, row: Int, onOpen: (Course) -> Unit) {
    Box(Modifier.fillMaxWidth().height(174.dp)) {
        Box(
            Modifier.fillMaxWidth().height(18.dp).align(Alignment.BottomCenter)
                .shadow(7.dp, RoundedCornerShape(3.dp))
                .background(Brush.verticalGradient(listOf(Color(0xFFB88A58), Color(0xFF68442F), Color(0xFF3A241C)))),
        )
        Row(
            modifier = Modifier.fillMaxWidth().align(Alignment.BottomCenter).padding(bottom = 17.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            courses.forEachIndexed { index, course ->
                Box(Modifier.weight(1f).height(150.dp), contentAlignment = Alignment.BottomCenter) {
                    CourseSpine(course, row * 3 + index, onOpen)
                }
            }
            repeat(3 - courses.size) { Box(Modifier.weight(1f)) }
        }
        Box(Modifier.fillMaxWidth().height(2.dp).align(Alignment.BottomCenter).background(Color(0xFFE4BD7C).copy(alpha = .65f)))
    }
}

@Composable
private fun CourseSpine(course: Course, index: Int, onOpen: (Course) -> Unit) {
    val color = bookColors[index % bookColors.size]
    Box(
        modifier = Modifier.width(54.dp).height((119 + index % 3 * 6).dp)
            .graphicsLayer(rotationZ = -42f, transformOrigin = TransformOrigin.Center)
            .shadow(7.dp, RoundedCornerShape(4.dp))
            .clip(RoundedCornerShape(4.dp))
            .background(Brush.horizontalGradient(listOf(color.copy(alpha = .84f), color, Color(0xFF172B28))))
            .border(1.dp, Color(0xDDE4CFA4), RoundedCornerShape(4.dp))
            .clickable(onClickLabel = "打开${course.name}") { onOpen(course) },
    ) {
        Box(Modifier.width(5.dp).fillMaxHeight().align(Alignment.CenterEnd).background(Color.White.copy(alpha = .18f)))
        Box(Modifier.fillMaxWidth().height(2.dp).align(Alignment.TopCenter).padding(horizontal = 5.dp).background(Color(0xFFEBD5A8)))
        Text(
            course.name,
            modifier = Modifier.align(Alignment.Center).width(108.dp).graphicsLayer(rotationZ = 90f),
            color = Color(0xFFFFF4D8), fontSize = 11.sp, fontWeight = FontWeight.Bold,
            maxLines = 1, overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun LibraryAction(label: String, onClick: () -> Unit, busy: Boolean = false) {
    Box(
        Modifier.fillMaxWidth().height(46.dp).clip(RoundedCornerShape(14.dp))
            .background(libraryGreen).clickable(enabled = !busy, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (busy) Icon(Icons.Default.Refresh, contentDescription = null, tint = Color.White, modifier = Modifier.size(18.dp))
            Text(if (busy) "正在同步…" else label, color = Color.White, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun LibraryNote(title: String, body: String) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp))
            .background(Color(0xD7F5F2E8)).padding(17.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text(title, color = libraryGreen, fontWeight = FontWeight.Bold, fontSize = 15.sp)
        Text(body, color = Color(0xFF596B61), fontSize = 12.sp)
    }
}

package com.example.campusai.ui.screens.classrooms

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Tv
import androidx.compose.material.icons.filled.TvOff
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.ClassroomAvailability
import com.example.campusai.data.model.ClassroomQuery
import com.example.campusai.data.repository.ClassroomRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.components.FormSwitchRow
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.MultiSelectChipRow
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ClassroomsScreen(
    repository: ClassroomRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
) {
    val loading by repository.loading.collectAsState()
    val error by repository.error.collectAsState()
    val scope = rememberCoroutineScope()

    val dateOptions = remember {
        repository.availableDates(System.currentTimeMillis()).map { date ->
            date.format(DateTimeFormatter.ofPattern("M月d日 EEEE")) to date.toString()
        }
    }
    val slotOptions = repository.slots()

    var campus by remember { mutableStateOf<String?>(null) }
    var building by remember { mutableStateOf<String?>(null) }
    var date by remember { mutableStateOf<String?>(null) }
    var selectedSlots by remember { mutableStateOf(setOf<Int>()) }
    var capacityFilter by remember { mutableStateOf(CampusStrings.Classrooms.CAPACITY_ALL) }
    var multimediaOnly by remember { mutableStateOf(false) }
    var hint by remember { mutableStateOf<String?>(null) }
    var results by remember { mutableStateOf<List<ClassroomAvailability>?>(null) }
    var detailItem by remember { mutableStateOf<ClassroomAvailability?>(null) }

    val capacityOptions = listOf(
        CampusStrings.Classrooms.CAPACITY_ALL, "≥ 40 座", "≥ 80 座", "≥ 100 座",
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(
            title = CampusStrings.Classrooms.TITLE,
            subtitle = CampusStrings.Classrooms.SUBTITLE,
            onBack = onBack,
        )
        Spacer(Modifier.height(14.dp))
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(
                bottom = WindowInsets.navigationBars.asPaddingValues()
                    .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
            ),
        ) {
            item {
                CampusCard(modifier = Modifier.enterAnimation(enabled = !reduceMotion)) {
                    FormField(label = CampusStrings.Classrooms.CAMPUS) {
                        FormDropdown(
                            options = repository.campuses(),
                            selected = campus,
                            onSelect = {
                                campus = it
                                building = null
                            },
                            placeholder = "请选择校区",
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    FormField(label = CampusStrings.Classrooms.BUILDING) {
                        FormDropdown(
                            options = campus?.let { repository.buildings(it) }.orEmpty(),
                            selected = building,
                            onSelect = { building = it },
                            placeholder = if (campus == null) "请先选择校区" else "请选择教学楼",
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    FormField(label = CampusStrings.Classrooms.DATE) {
                        FormDropdown(
                            options = dateOptions.map { it.first },
                            selected = dateOptions.firstOrNull { it.second == date }?.first,
                            onSelect = { label -> date = dateOptions.first { it.first == label }.second },
                            placeholder = "请选择日期",
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    FormField(label = CampusStrings.Classrooms.SLOTS) {
                        MultiSelectChipRow(
                            options = slotOptions.map { it.label },
                            selected = selectedSlots.map { idx -> slotOptions.first { it.index == idx }.label }.toSet(),
                            onToggle = { label ->
                                val idx = slotOptions.first { it.label == label }.index
                                selectedSlots = if (idx in selectedSlots) selectedSlots - idx else selectedSlots + idx
                            },
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    FormField(label = CampusStrings.Classrooms.CAPACITY) {
                        FilterChipRow(
                            options = capacityOptions,
                            selected = capacityFilter,
                            onSelect = { capacityFilter = it },
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    FormSwitchRow(
                        title = CampusStrings.Classrooms.MULTIMEDIA,
                        subtitle = "投影、音响等教学设备",
                        checked = multimediaOnly,
                        onCheckedChange = { multimediaOnly = it },
                    )
                    if (hint != null) {
                        Spacer(Modifier.height(10.dp))
                        Text(hint.orEmpty(), color = Primary, fontSize = 12.sp)
                    }
                    Spacer(Modifier.height(14.dp))
                    CampusPrimaryButton(
                        text = CampusStrings.Classrooms.QUERY,
                        onClick = {
                            val query = ClassroomQuery(
                                campus = campus,
                                building = building,
                                date = date,
                                slotIndexes = selectedSlots,
                                minCapacity = capacityOptions.indexOf(capacityFilter).let {
                                    when (it) {
                                        1 -> 40
                                        2 -> 80
                                        3 -> 100
                                        else -> 0
                                    }
                                },
                                multimediaOnly = multimediaOnly,
                            )
                            if (!query.isComplete()) {
                                hint = CampusStrings.Classrooms.INCOMPLETE
                                return@CampusPrimaryButton
                            }
                            hint = null
                            scope.launch {
                                runCatching { repository.query(query) }
                                    .onSuccess { results = it }
                                    .onFailure { hint = CampusStrings.Classrooms.INCOMPLETE }
                            }
                        },
                    )
                }
            }

            when {
                loading -> item { LoadingState() }
                error != null -> item {
                    ErrorState(error.orEmpty(), onRetry = { hint = CampusStrings.Classrooms.INCOMPLETE })
                }
                results != null -> {
                    val list = results.orEmpty()
                    item {
                        Text(
                            "${CampusStrings.Classrooms.RESULT_TITLE}（${list.size}）",
                            color = TextPrimary,
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                        )
                    }
                    if (list.isEmpty()) {
                        item { EmptyState(Icons.Default.MeetingRoom, CampusStrings.Classrooms.EMPTY) }
                    } else {
                        items(list, key = { it.classroom.id }) { item ->
                            ClassroomRow(item, onClick = { detailItem = item })
                        }
                    }
                }
            }
        }
    }

    if (detailItem != null) {
        ModalBottomSheet(
            onDismissRequest = { detailItem = null },
            sheetState = rememberModalBottomSheetState(),
            containerColor = Surface,
        ) {
            val item = detailItem!!
            Column(Modifier.padding(horizontal = 20.dp)) {
                Text(item.classroom.name, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.People, null, tint = Primary, modifier = Modifier.size(16.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(
                        "容量 ${item.classroom.capacity} ${CampusStrings.Classrooms.SEAT_UNIT} · ${item.classroom.floor} ${CampusStrings.Classrooms.FLOOR_UNIT}",
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        if (item.classroom.hasMultimedia) Icons.Default.Tv else Icons.Default.TvOff,
                        null,
                        tint = Primary,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        if (item.classroom.hasMultimedia) CampusStrings.Classrooms.HAS_MULTIMEDIA else CampusStrings.Classrooms.NO_MULTIMEDIA,
                        color = Muted,
                        fontSize = 12.sp,
                    )
                }
                Spacer(Modifier.height(14.dp))
                Text(CampusStrings.Classrooms.DETAIL_FREE, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(8.dp))
                item.freeSlots.forEach { slot ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 5.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        StatusTag(slot.label, StatusTone.INFO)
                        Spacer(Modifier.width(10.dp))
                        Text(slot.timeRange, color = Muted, fontSize = 12.sp)
                    }
                }
                Spacer(Modifier.height(28.dp))
            }
        }
    }
}

@Composable
private fun ClassroomRow(item: ClassroomAvailability, onClick: () -> Unit) {
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onClick),
        padding = PaddingValues(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(item.classroom.name, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(5.dp))
                Text(
                    "${item.classroom.floor} ${CampusStrings.Classrooms.FLOOR_UNIT} · " +
                        "${item.classroom.capacity} ${CampusStrings.Classrooms.SEAT_UNIT} · " +
                        if (item.classroom.hasMultimedia) CampusStrings.Classrooms.HAS_MULTIMEDIA else CampusStrings.Classrooms.NO_MULTIMEDIA,
                    color = Muted,
                    fontSize = 12.sp,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                StatusTag(
                    "${item.freeSlots.size} 个空闲节次",
                    StatusTone.SUCCESS,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    item.freeSlots.take(2).joinToString("  ") { it.label } +
                        if (item.freeSlots.size > 2) " …" else "",
                    color = Primary,
                    fontSize = 11.sp,
                )
            }
        }
    }
}

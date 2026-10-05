package com.example.campusai.ui.screens.tasks

import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight

@Composable
fun TaskCalendarScreen(repository: AppRepository, onBack: () -> Unit, onOpenTask: (String) -> Unit) {
    val tasks by repository.tasks.collectAsStateWithLifecycle()
    Box(Modifier.fillMaxSize()) {
        JournalBackdrop(Modifier.fillMaxSize())
        LazyColumn(
            Modifier.fillMaxSize().padding(start = 12.dp, end = 22.dp, top = 7.dp).journalBookPage(),
            contentPadding = PaddingValues(start = 28.dp, top = 23.dp, end = 16.dp, bottom = BottomDockReservedHeight + 20.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    Text("CAMPUS / TASK JOURNAL", color = JournalClay, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CalendarMonth, null, tint = JournalBlue)
                        Spacer(Modifier.width(9.dp))
                        Text("任务时间线", color = JournalNight, fontWeight = FontWeight.ExtraBold, fontSize = 23.sp)
                    }
                    Text("按截止时间查阅任务，点开一项查看完整记录。", color = JournalMuted, fontSize = 12.sp)
                    HorizontalDivider(color = JournalBlue.copy(alpha = .45f))
                }
            }
            if (tasks.isEmpty()) item { Text("还没有任务记录", Modifier.fillMaxWidth().padding(vertical = 32.dp), color = JournalMuted) }
            itemsIndexed(tasks, key = { index, task -> "calendar-task|${task.id.ifBlank { task.title }}|$index" }) { _, task ->
                Column(Modifier.fillMaxWidth().clickable { onOpenTask(Uri.encode(task.id)) }.padding(vertical = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(task.title, fontWeight = FontWeight.Bold, color = JournalNight, fontSize = 15.sp)
                    Text("${task.due}   ·   ${if (task.done) "已完成" else "待完成"}", color = JournalMuted, fontSize = 12.sp)
                    HorizontalDivider(color = JournalBlue.copy(alpha = .35f))
                }
            }
        }
    }
}

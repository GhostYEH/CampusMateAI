package com.example.campusai.ui.screens.courses

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.campusai.data.classroom.nativeplayer.NativeClassroomRef
import com.example.campusai.data.model.Course
import com.example.campusai.data.remote.MagicClassWorkspaceDto
import com.example.campusai.data.remote.MagicClassWorkspaceStageSummaryDto
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.screens.courses.nativeplayer.NativeClassroomPlayer
import kotlinx.coroutines.launch

/**
 * 课程页的受管课堂入口。
 *
 * 经典课堂接口只有 URL + composition 摘要，无法原生渲染；这里只列真实受管
 * workspace/stage（作业复习同一数据源），点击后才读取完整 stage 与 playback。
 */
@Composable
fun ManagedClassroomSection(course: Course, repository: AppRepository) {
    var workspaces by remember(course.id) { mutableStateOf<List<MagicClassWorkspaceDto>>(emptyList()) }
    var loading by remember(course.id) { mutableStateOf(true) }
    var error by remember(course.id) { mutableStateOf<String?>(null) }
    var expandedWorkspace by remember(course.id) { mutableStateOf<String?>(null) }
    var stagesByWorkspace by remember(course.id) {
        mutableStateOf<Map<String, List<MagicClassWorkspaceStageSummaryDto>>>(emptyMap())
    }
    var loadingStages by remember(course.id) { mutableStateOf<String?>(null) }
    var openRef by rememberSaveable(course.id) { mutableStateOf<NativeClassroomRef?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(course.id) {
        loading = true
        repository.magicClassWorkspaces(course.id)
            .onSuccess {
                workspaces = it
                error = null
            }
            .onFailure {
                workspaces = emptyList()
                error = it.message
            }
        loading = false
    }

    fun loadStages(workspace: MagicClassWorkspaceDto) {
        if (stagesByWorkspace[workspace.id] != null || loadingStages != null) return
        loadingStages = workspace.id
        scope.launch {
            repository.magicClassStages(course.id, workspace.id)
                .onSuccess { stagesByWorkspace = stagesByWorkspace + (workspace.id to it) }
                .onFailure { error = it.message ?: "课堂目录读取失败" }
            loadingStages = null
        }
    }

    if (!loading && workspaces.isEmpty() && openRef == null) {
        // 没有受管课堂时不占页面；错误只在已有入口时以一行提示出现。
        if (error != null) {
            Text(
                "受管课堂暂时不可用：${error.orEmpty()}",
                color = ManagedMuted,
                fontSize = 11.sp,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        return
    }

    Column(
        Modifier.fillMaxWidth().padding(top = 10.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        androidx.compose.material3.HorizontalDivider(color = ManagedLine)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("受管课堂", color = ManagedInk, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Text("真实课件 · 原生翻页与互动", color = ManagedMuted, fontSize = 11.sp)
            }
            if (loading) {
                CircularProgressIndicator(Modifier.size(16.dp), color = ManagedCopper, strokeWidth = 2.dp)
            }
        }
        workspaces.forEach { workspace ->
            val expanded = expandedWorkspace == workspace.id
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(if (expanded) Color(0xFFF0E8D7) else Color(0xFFFFFEF8), RoundedCornerShape(10.dp))
                    .border(1.dp, ManagedLine, RoundedCornerShape(10.dp))
                    .padding(10.dp),
            ) {
                Row(
                    Modifier.fillMaxWidth().clickable {
                        expandedWorkspace = if (expanded) null else workspace.id
                        if (!expanded) loadStages(workspace)
                    },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            workspace.name.ifBlank { "课堂工作台" },
                            color = ManagedInk,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                        if (workspace.description.isNotBlank()) {
                            Text(workspace.description, color = ManagedMuted, fontSize = 10.sp, maxLines = 2)
                        }
                    }
                    Text(if (expanded) "收起" else "展开", color = ManagedCopper, fontSize = 11.sp)
                }
                if (expanded) {
                    Spacer(Modifier.height(6.dp))
                    val stageLoading = loadingStages == workspace.id
                    if (stageLoading) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(Modifier.size(14.dp), color = ManagedCopper, strokeWidth = 2.dp)
                            Spacer(Modifier.width(6.dp))
                            Text("读取课堂舞台…", color = ManagedMuted, fontSize = 10.sp)
                        }
                    }
                    val stages = stagesByWorkspace[workspace.id].orEmpty()
                    if (!stageLoading && stages.isEmpty()) {
                        Text("这个工作台还没有可阅读的舞台。", color = ManagedMuted, fontSize = 10.sp)
                    }
                    stages.forEach { stage ->
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(top = 6.dp)
                                .background(Color(0xFFFFFEF8), RoundedCornerShape(8.dp))
                                .padding(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(stage.title.orEmpty().ifBlank { "未命名课堂" }, color = ManagedInk, fontSize = 12.sp)
                                Text("revision ${stage.revision}", color = ManagedMuted, fontSize = 9.sp)
                            }
                            TextButton(
                                onClick = {
                                    openRef = NativeClassroomRef(
                                        courseId = course.id,
                                        workspaceId = workspace.id,
                                        stageId = stage.id,
                                        title = stage.title.orEmpty(),
                                        workspaceName = workspace.name,
                                    )
                                },
                            ) {
                                Text("进入", color = ManagedCopper, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }
    }

    openRef?.let { ref ->
        Dialog(
            onDismissRequest = { openRef = null },
            properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
        ) {
            Surface(Modifier.fillMaxSize(), color = Color(0xFFF1F3EA)) {
                NativeClassroomPlayer(
                    ref = ref,
                    repository = repository,
                    onClose = { openRef = null },
                    onOpenFallback = { openRef = null },
                )
            }
        }
    }
}


private val ManagedInk = Color(0xFF263A50)
private val ManagedCopper = Color(0xFFAD6845)
private val ManagedLine = Color(0xFFD4BC91)
private val ManagedMuted = Color(0xFF667487)

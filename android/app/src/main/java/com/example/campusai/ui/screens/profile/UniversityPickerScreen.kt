package com.example.campusai.ui.screens.profile

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

/**
 * 个人资料编辑页内嵌的「所在大学」选择页。
 *
 * 复用 AppRepository.loadUniversities（即现有 GET /universities 能力），
 * 不重新造大学数据库。用户点击某所大学后，**不立即调用** PUT /profile/university，
 * 而是通过 [onSelected] 把 id + name 回调给 AccountScreen 暂存到 Form State，
 * 等 AccountScreen 点「保存」时再统一提交，符合「选择 → 返回编辑页 → 保存」流程。
 */
@Composable
fun UniversityPickerScreen(
    repository: AppRepository,
    currentUniversityId: String,
    onSelected: (id: String, name: String) -> Unit,
    onBack: () -> Unit,
) {
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    var query by remember { mutableStateOf("") }
    var universities by remember { mutableStateOf(emptyList<com.example.campusai.data.remote.UniversityDto>()) }
    var loading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        loading = true
        errorMessage = null
        runCatching { repository.loadUniversities(query) }
            .onSuccess { universities = it }
            .onFailure { errorMessage = it.message ?: "大学列表加载失败" }
        loading = false
    }
    LaunchedEffect(Unit) { load() }

    Box(Modifier.fillMaxSize().background(ReferencePageBackground)) {
        Column(
            Modifier.fillMaxSize().padding(bottom = BottomDockReservedHeight + 28.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 12.dp)
                    .enterAnimation(enabled = !reduceMotion),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.Default.ArrowBack, "返回", tint = ReferenceText)
                }
                Column(Modifier.padding(start = 4.dp)) {
                    Text("选择所在大学", color = ReferenceText, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Text("搜索后点击学校即可返回编辑页", color = ReferenceMuted, fontSize = 12.sp)
                }
            }
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp),
                label = { Text("搜索大学名称") },
                leadingIcon = { Icon(Icons.Default.Search, null, tint = ReferencePrimary) },
                trailingIcon = {
                    IconButton(onClick = { scope.launch { load() } }) {
                        Icon(Icons.Default.ArrowForward, "搜索", tint = ReferencePrimary)
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = ReferencePrimary,
                    unfocusedBorderColor = ReferenceDivider,
                    focusedContainerColor = ReferenceSurface,
                    unfocusedContainerColor = ReferenceSurface,
                    focusedTextColor = ReferenceText,
                    unfocusedTextColor = ReferenceText,
                    focusedLabelColor = ReferencePrimary,
                    unfocusedLabelColor = ReferenceMuted,
                ),
            )
            when {
                loading -> {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 18.dp))
                }
                errorMessage != null -> {
                    ErrorRow(
                        message = errorMessage!!,
                        onRetry = { scope.launch { load() } },
                    )
                }
                universities.isEmpty() -> {
                    EmptyRow("未找到匹配的大学，换个关键词试试")
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize().weight(1f),
                        contentPadding = PaddingValues(horizontal = 18.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        items(universities, key = { it.id }) { university ->
                            UniversityRow(
                                name = university.name,
                                subtitle = listOfNotNull(university.province, university.city)
                                    .joinToString(" · ").ifBlank { "中国" },
                                isCurrent = university.id == currentUniversityId,
                                onClick = { onSelected(university.id, university.name) },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun UniversityRow(
    name: String,
    subtitle: String,
    isCurrent: Boolean,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(ReferenceSurface)
            .campusClickable(onClick = onClick).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(42.dp).background(ReferencePrimarySoft, RoundedCornerShape(13.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Default.School, null, tint = ReferencePrimary, modifier = Modifier.size(22.dp))
        }
        Column(Modifier.padding(start = 14.dp).weight(1f)) {
            Text(name, color = ReferenceText, fontWeight = FontWeight.SemiBold, fontSize = 15.sp)
            Text(subtitle, color = ReferenceMuted, fontSize = 12.sp)
        }
        if (isCurrent) {
            AssistChip(
                onClick = {},
                label = { Text("当前") },
                leadingIcon = { Icon(Icons.Default.CheckCircle, null, Modifier.size(16.dp)) },
            )
        } else {
            Icon(Icons.Default.ChevronRight, null, tint = ReferenceMuted, modifier = Modifier.size(20.dp))
        }
    }
}

@Composable
private fun EmptyRow(text: String) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 24.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.SearchOff, null, tint = ReferenceMuted)
        Text(text, Modifier.padding(start = 8.dp), color = ReferenceMuted, fontSize = 13.sp)
    }
}

@Composable
private fun ErrorRow(message: String, onRetry: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 12.dp)
            .clip(RoundedCornerShape(16.dp)).background(ReferenceSurface).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.ErrorOutline, null, tint = DangerText)
            Text(
                message,
                Modifier.padding(start = 8.dp).weight(1f),
                color = ReferenceText,
                fontSize = 13.sp,
            )
        }
        TextButton(onClick = onRetry) {
            Icon(Icons.Default.Refresh, null, Modifier.size(16.dp))
            Spacer(Modifier.width(4.dp))
            Text("重试")
        }
    }
}
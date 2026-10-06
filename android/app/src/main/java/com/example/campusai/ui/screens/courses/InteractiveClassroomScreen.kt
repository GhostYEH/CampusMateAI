package com.example.campusai.ui.screens.courses

import androidx.compose.foundation.background
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.R
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Muted

@Composable
fun InteractiveClassroomScreen(
    courseId: String,
    repository: AppRepository,
    onBack: () -> Unit,
    initialSessionId: String? = null,
) {
    val courses by repository.courses.collectAsStateWithLifecycle()
    val course = courses.firstOrNull { it.id == courseId }
    var loadingCourse by remember(courseId) { mutableStateOf(true) }
    LaunchedEffect(courseId) {
        try { repository.refreshCourses() }
        finally { loadingCourse = false }
    }

    Box(Modifier.fillMaxSize()) {
        Image(painter = painterResource(R.drawable.classroom_evening_interior), contentDescription = null,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xB3152036), Color(0xD31A2037)))))
        LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 20.dp,
            top = 18.dp,
            end = 20.dp,
            bottom = floatingDockContentBottomPadding(
                androidx.compose.foundation.layout.WindowInsets.navigationBars
                    .asPaddingValues().calculateBottomPadding(),
            ) + 24.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Row(Modifier.fillMaxWidth().padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "返回课程", tint = Color.White) }
                Column(Modifier.padding(start = 6.dp).weight(1f)) {
                    Text("互动课堂", color = Color.White, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                    Text(course?.name ?: "正在读取课程…", color = Color(0xFFF1D4A3), fontSize = 12.sp)
                }
            }
        }
        if (course == null && loadingCourse) {
            item {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                    CircularProgressIndicator(Modifier.size(24.dp), color = Color(0xFFE7BE75), strokeWidth = 2.dp)
                }
            }
        } else if (course == null) {
            item { Text("找不到这门课，请返回图书馆重新同步课程。", color = Color.White, fontSize = 13.sp) }
        } else {
            item {
                Column(Modifier.fillMaxWidth().background(Color(0xFFF5EEDC), RoundedCornerShape(topStart = 8.dp, topEnd = 26.dp, bottomEnd = 8.dp, bottomStart = 8.dp))
                    .border(1.dp, Color(0xFFD4BC91), RoundedCornerShape(topStart = 8.dp, topEnd = 26.dp, bottomEnd = 8.dp, bottomStart = 8.dp))
                    .padding(17.dp)) {
                    InteractiveClassroomSection(
                        course = course,
                        repository = repository,
                        initialSessionId = initialSessionId,
                    )
                }
            }
        }
        }
    }
}

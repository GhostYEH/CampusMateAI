package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.Teacher
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch
import java.util.UUID

@Composable
fun TeachersScreen(
    repository: AppRepository,
    onBack: () -> Unit,
) {
    val user by repository.session.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val darkMode by repository.darkMode.collectAsState()
    val teachers = user?.teachers ?: emptyList()
    val scope = rememberCoroutineScope()
    
    var editingTeacher by remember { mutableStateOf<Teacher?>(null) }
    var isAdding by remember { mutableStateOf(false) }

    ReferenceSystemBars(darkMode)

    Box(Modifier.fillMaxSize().background(ReferencePageBackground).imePadding()) {
        Column(Modifier.fillMaxSize()) {
            ReferenceSubpageHeader("我的老师", "管理任课教师联系方式", onBack)
            
            if (teachers.isEmpty()) {
                Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.SupervisorAccount, null, tint = ReferenceMuted, modifier = Modifier.size(48.dp))
                        Spacer(Modifier.height(12.dp))
                        Text("暂无老师信息", color = ReferenceMuted, fontSize = 14.sp)
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(top = 16.dp, bottom = 88.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    items(teachers, key = { it.id }) { teacher ->
                        TeacherCard(
                            teacher = teacher,
                            onEdit = { editingTeacher = teacher },
                            onDelete = {
                                val updated = teachers.filter { it.id != teacher.id }
                                scope.launch { repository.updateUser(user!!.copy(teachers = updated)) }
                            },
                            modifier = Modifier.enterAnimation(enabled = !reduceMotion)
                        )
                    }
                }
            }
        }
        
        FloatingActionButton(
            onClick = { isAdding = true },
            modifier = Modifier.align(Alignment.BottomEnd).padding(24.dp),
            containerColor = ReferencePrimary,
            contentColor = Color.White,
            shape = RoundedCornerShape(16.dp)
        ) {
            Icon(Icons.Default.Add, "添加老师")
        }
    }
    
    if (isAdding || editingTeacher != null) {
        TeacherEditDialog(
            teacher = editingTeacher,
            onDismiss = {
                isAdding = false
                editingTeacher = null
            },
            onSave = { updatedTeacher ->
                val newTeachers = if (isAdding) {
                    teachers + updatedTeacher
                } else {
                    teachers.map { if (it.id == updatedTeacher.id) updatedTeacher else it }
                }
                scope.launch { repository.updateUser(user!!.copy(teachers = newTeachers)) }
                isAdding = false
                editingTeacher = null
            }
        )
    }
}

@Composable
private fun TeacherCard(
    teacher: Teacher,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    Column(
        modifier.padding(horizontal = 18.dp).fillMaxWidth()
            .shadow(
                elevation = 12.dp,
                shape = RoundedCornerShape(22.dp),
                ambientColor = ReferencePrimary.copy(alpha = .07f),
                spotColor = ReferencePrimary.copy(alpha = .1f),
            )
            .clip(RoundedCornerShape(22.dp))
            .background(ReferenceSurface)
            .clickable(onClick = onEdit)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(40.dp).clip(CircleShape).background(ReferencePrimarySoft),
                contentAlignment = Alignment.Center
            ) {
                Text(teacher.name.take(1), color = ReferencePrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(teacher.name, color = ReferenceText, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                if (teacher.subject.isNotBlank()) {
                    Text(teacher.subject, color = ReferenceMuted, fontSize = 12.sp)
                }
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Default.Delete, "删除", tint = DangerText)
            }
        }
        
        if (teacher.email.isNotBlank()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Email, null, tint = ReferenceMuted, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(8.dp))
                Text(teacher.email, color = ReferenceText, fontSize = 13.sp)
            }
        }
        if (teacher.phone.isNotBlank()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Phone, null, tint = ReferenceMuted, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(8.dp))
                Text(teacher.phone, color = ReferenceText, fontSize = 13.sp)
            }
        }
        if (teacher.notes.isNotBlank()) {
            Row(verticalAlignment = Alignment.Top) {
                Icon(Icons.Default.Info, null, tint = ReferenceMuted, modifier = Modifier.size(16.dp).padding(top = 2.dp))
                Spacer(Modifier.width(8.dp))
                Text(teacher.notes, color = ReferenceMuted, fontSize = 12.sp, lineHeight = 16.sp)
            }
        }
    }
}

@Composable
private fun TeacherEditDialog(
    teacher: Teacher?,
    onDismiss: () -> Unit,
    onSave: (Teacher) -> Unit
) {
    var name by remember { mutableStateOf(teacher?.name.orEmpty()) }
    var subject by remember { mutableStateOf(teacher?.subject.orEmpty()) }
    var email by remember { mutableStateOf(teacher?.email.orEmpty()) }
    var phone by remember { mutableStateOf(teacher?.phone.orEmpty()) }
    var notes by remember { mutableStateOf(teacher?.notes.orEmpty()) }
    
    val focusManager = LocalFocusManager.current
    
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = ReferenceSurface,
        title = {
            Text(if (teacher == null) "添加老师" else "编辑信息", color = ReferenceText, fontWeight = FontWeight.Bold, fontSize = 18.sp)
        },
        text = {
            Column(
                Modifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                TeacherFormField(
                    value = name,
                    onValueChange = { name = it },
                    label = "姓名",
                    icon = Icons.Default.Person,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) }
                )
                TeacherFormField(
                    value = subject,
                    onValueChange = { subject = it },
                    label = "科目",
                    icon = Icons.Default.Info,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) }
                )
                TeacherFormField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = "电话",
                    icon = Icons.Default.Phone,
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) }
                )
                TeacherFormField(
                    value = email,
                    onValueChange = { email = it },
                    label = "邮箱",
                    icon = Icons.Default.Email,
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) }
                )
                TeacherFormField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = "备注",
                    icon = Icons.Default.Edit,
                    imeAction = ImeAction.Done,
                    onIme = { focusManager.clearFocus() }
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    if (name.isNotBlank()) {
                        onSave(
                            Teacher(
                                id = teacher?.id ?: UUID.randomUUID().toString(),
                                name = name.trim(),
                                subject = subject.trim(),
                                email = email.trim(),
                                phone = phone.trim(),
                                notes = notes.trim()
                            )
                        )
                    }
                },
                enabled = name.isNotBlank()
            ) {
                Text("保存", color = if (name.isNotBlank()) ReferencePrimary else ReferenceMuted, fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消", color = ReferenceMuted)
            }
        }
    )
}

@Composable
private fun TeacherFormField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    icon: ImageVector,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction,
    onIme: () -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        leadingIcon = { Icon(icon, null, tint = ReferencePrimary, modifier = Modifier.size(20.dp)) },
        singleLine = true,
        shape = RoundedCornerShape(14.dp),
        keyboardOptions = KeyboardOptions(keyboardType = keyboardType, imeAction = imeAction),
        keyboardActions = KeyboardActions(onNext = { onIme() }, onDone = { onIme() }),
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
}

package com.example.campusai.ui.screens.profile

import com.example.campusai.ui.components.GlassButton as Button

import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.activity.compose.BackHandler

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
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
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun AccountScreen(
    repository: AppRepository,
    onBack: () -> Unit,
    onPickUniversity: () -> Unit = {},
    pickedUniversityId: String? = null,
    pickedUniversityName: String? = null,
    onConsumePicked: () -> Unit = {},
) {
    val user by repository.session.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    var name by remember(user) { mutableStateOf(user?.name.orEmpty()) }
    var detail by remember(user) { mutableStateOf(user?.detail.orEmpty()) }
    var studentId by remember(user) { mutableStateOf(user?.studentId.orEmpty()) }
    var email by remember(user) { mutableStateOf(user?.email.orEmpty()) }
    var phone by remember(user) { mutableStateOf(user?.phone.orEmpty()) }
    var universityId by remember(user) { mutableStateOf(user?.universityId.orEmpty()) }
    var universityName by remember(user) { mutableStateOf(user?.universityName.orEmpty()) }
    var saving by remember { mutableStateOf(false) }
    var nameError by remember { mutableStateOf<String?>(null) }
    var emailError by remember { mutableStateOf<String?>(null) }
    var showDiscard by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    val hasUnsavedChanges = name != user?.name.orEmpty() || detail != user?.detail.orEmpty() ||
        studentId != user?.studentId.orEmpty() || email != user?.email.orEmpty() ||
        phone != user?.phone.orEmpty() || universityId != user?.universityId.orEmpty()
    fun leave() { if (hasUnsavedChanges) showDiscard = true else onBack() }
    BackHandler(onBack = ::leave)

    LaunchedEffect(Unit) {
        runCatching { repository.ensureUniversityNameLoaded() }
    }
    LaunchedEffect(pickedUniversityId, pickedUniversityName) {
        if (pickedUniversityId != null && pickedUniversityName != null) {
            universityId = pickedUniversityId
            universityName = pickedUniversityName
            onConsumePicked()
        }
    }

    fun save() {
        nameError = if (name.trim().length < 2) "姓名至少需要 2 个字" else null
        emailError = if (email.isNotBlank() && (!email.contains("@") || !email.substringAfter("@").contains("."))) {
            "请输入有效的邮箱地址"
        } else null
        if (nameError != null || emailError != null || saving) return
        saving = true
        focusManager.clearFocus()
        scope.launch {
            runCatching {
                val current = repository.session.value
                if (universityId.isNotBlank() && current?.universityId != universityId) {
                    repository.updateUniversity(universityId, universityName)
                }
                repository.updateProfile(name, detail, email, phone, studentId)
            }.onSuccess {
                snackbar.showSnackbar("账号资料已保存")
            }.onFailure {
                snackbar.showSnackbar("保存失败，请稍后重试")
            }
            saving = false
        }
    }

    Box(Modifier.fillMaxSize().background(Color(0xFFF8F2E8)).imePadding()) {
        Column(
            Modifier.fillMaxSize().statusBarsPadding().verticalScroll(rememberScrollState())
                .padding(bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 28.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Row(Modifier.fillMaxWidth().padding(start = 12.dp, top = 8.dp, end = 18.dp),
                verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = ::leave) {
                    Icon(Icons.Default.ArrowBack, contentDescription = "返回我的", tint = Color(0xFF203B32))
                }
                Text("账号设置", color = Color(0xFF203B32), fontSize = 22.sp,
                    fontWeight = FontWeight.Bold)
            }
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 18.dp)
                    .enterAnimation(enabled = !reduceMotion),
                horizontalArrangement = Arrangement.Center,
            ) {
                ReferenceAvatar(86.dp)
            }

            AccountCard(
                title = "基本信息",
                modifier = Modifier.enterAnimation(delayMs = 60, enabled = !reduceMotion),
            ) {
                AccountField(
                    value = name,
                    onValueChange = {
                        name = it.take(20)
                        nameError = null
                    },
                    label = "姓名",
                    icon = Icons.Default.Person,
                    error = nameError,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) },
                )
                AccountField(
                    value = studentId,
                    onValueChange = { studentId = it.take(24) },
                    label = if (user?.role == "teacher") "工号" else "学号",
                    icon = Icons.Default.Badge,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) },
                )
                AccountField(
                    value = detail,
                    onValueChange = { detail = it.take(40) },
                    label = "院系与年级",
                    icon = Icons.Default.School,
                    supporting = "例如：计算机学院 · 大三",
                    multiline = true,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) },
                )
                UniversityField(
                    value = universityName,
                    onClick = onPickUniversity,
                )
            }

            AccountCard(
                title = "联系方式",
                modifier = Modifier.enterAnimation(delayMs = 120, enabled = !reduceMotion),
            ) {
                AccountField(
                    value = email,
                    onValueChange = {
                        email = it.take(60)
                        emailError = null
                    },
                    label = "校园邮箱",
                    icon = Icons.Default.Email,
                    error = emailError,
                    keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) },
                )
                AccountField(
                    value = phone,
                    onValueChange = {
                        phone = it.filter { char -> char.isDigit() || char == ' ' || char == '-' }.take(20)
                    },
                    label = "手机号码",
                    icon = Icons.Default.Phone,
                    keyboardType = KeyboardType.Phone,
                    imeAction = ImeAction.Done,
                    onIme = ::save,
                )
                Text(
                    "联系方式用于账号资料，请确认填写正确。",
                    color = ReferenceMuted,
                    fontSize = 10.5.sp,
                )
            }

            Button(
                onClick = ::save,
                enabled = !saving,
                modifier = Modifier.padding(horizontal = 18.dp).fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = ReferencePrimary),
            ) {
                if (saving) {
                    CircularProgressIndicator(color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(9.dp))
                    Text("正在保存…")
                } else {
                    Icon(Icons.Default.Save, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("保存账号资料", fontWeight = FontWeight.Bold)
                }
            }
        }
        SnackbarHost(
            snackbar,
            Modifier.align(Alignment.BottomCenter)
                .padding(start = 16.dp, end = 16.dp,
                    bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 16.dp),
        )
    }
    if (showDiscard) AlertDialog(
        onDismissRequest = { showDiscard = false },
        title = { Text("放弃未保存的修改？") },
        text = { Text("刚才修改的账号资料还没有保存。") },
        confirmButton = { TextButton(onClick = { showDiscard = false; onBack() }) { Text("放弃修改") } },
        dismissButton = { TextButton(onClick = { showDiscard = false }) { Text("继续编辑") } },
    )
}

@Composable
private fun AccountCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier.padding(horizontal = 18.dp).fillMaxWidth()
                .shadow(
                    elevation = 12.dp,
                    shape = RoundedCornerShape(22.dp),
                    ambientColor = ReferencePrimary.copy(alpha = .07f),
                    spotColor = ReferencePrimary.copy(alpha = .1f),
            )
            .clip(RoundedCornerShape(22.dp)).background(ReferenceSurface).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(13.dp),
    ) {
        ReferenceSectionLabel(title)
        content()
    }
}

@Composable
private fun AccountField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    icon: ImageVector,
    error: String? = null,
    supporting: String? = null,
    multiline: Boolean = false,
    keyboardType: KeyboardType = KeyboardType.Text,
    imeAction: ImeAction,
    onIme: () -> Unit,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        leadingIcon = { Icon(icon, null, tint = ReferencePrimary) },
        isError = error != null,
        supportingText = {
            val message = error ?: supporting
            if (message != null) {
                Text(message, color = if (error != null) DangerText else ReferenceMuted)
            }
        },
        singleLine = !multiline,
        maxLines = if (multiline) 3 else 1,
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

/**
 * 「所在大学」表单项。风格与 [AccountField]（OutlinedTextField）统一：
 * 同样的圆角边框、leadingIcon、label 占位、容器色与边框色。
 * 点击后进入 [UniversityPickerScreen]，不直接编辑。
 */
@Composable
private fun UniversityField(
    value: String,
    onClick: () -> Unit,
) {
    val hasValue = value.isNotBlank()
    Column {
        Row(
            Modifier.fillMaxWidth().height(56.dp).clip(RoundedCornerShape(14.dp))
                .background(ReferenceSurface).border(1.dp, ReferenceDivider, RoundedCornerShape(14.dp))
                .campusClickable(onClick = onClick).padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.School, null, tint = ReferencePrimary, modifier = Modifier.size(24.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "所在大学",
                    color = if (hasValue) ReferenceMuted else ReferencePrimary,
                    fontSize = 12.sp,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    if (hasValue) value else "点击选择所在大学",
                    color = if (hasValue) ReferenceText else ReferenceMuted,
                    fontSize = 16.sp,
                    maxLines = 1,
                )
            }
            Icon(Icons.Default.ChevronRight, null, tint = ReferenceMuted, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.height(4.dp))
        Text(
            "选择后保存才会生效，社区与教务数据将按大学隔离",
            color = ReferenceMuted,
            fontSize = 10.5.sp,
        )
    }
}

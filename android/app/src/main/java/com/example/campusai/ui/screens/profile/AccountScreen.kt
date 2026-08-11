package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
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
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun AccountScreen(
    repository: AppRepository,
    onBack: () -> Unit,
) {
    val user by repository.session.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val darkMode by repository.darkMode.collectAsState()
    var name by remember(user) { mutableStateOf(user?.name.orEmpty()) }
    var detail by remember(user) { mutableStateOf(user?.detail.orEmpty()) }
    var studentId by remember(user) { mutableStateOf(user?.studentId.orEmpty()) }
    var email by remember(user) { mutableStateOf(user?.email.orEmpty()) }
    var phone by remember(user) { mutableStateOf(user?.phone.orEmpty()) }
    var saving by remember { mutableStateOf(false) }
    var nameError by remember { mutableStateOf<String?>(null) }
    var emailError by remember { mutableStateOf<String?>(null) }
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    ReferenceSystemBars(darkMode)

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
                repository.updateProfile(name, detail, email, phone, studentId)
            }.onSuccess {
                snackbar.showSnackbar("账号资料已保存")
            }.onFailure {
                snackbar.showSnackbar("保存失败，请稍后重试")
            }
            saving = false
        }
    }

    Box(Modifier.fillMaxSize().background(ReferencePageBackground).imePadding()) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 18.dp)
                    .enterAnimation(enabled = !reduceMotion),
                horizontalArrangement = Arrangement.Center,
            ) {
                Box(contentAlignment = Alignment.BottomEnd) {
                    ReferenceAvatar(86.dp)
                    Box(
                        Modifier.size(27.dp).clip(CircleShape).background(ReferencePrimary),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Edit, null, tint = Color.White, modifier = Modifier.size(14.dp))
                    }
                }
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
                    imeAction = ImeAction.Next,
                    onIme = { focusManager.moveFocus(FocusDirection.Down) },
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
                    "当前资料仅保存在本机；接入真实后端后可同步到校园账号。",
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
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).padding(16.dp))
    }
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

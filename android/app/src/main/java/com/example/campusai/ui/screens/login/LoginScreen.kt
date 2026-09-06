package com.example.campusai.ui.screens.login

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.School
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.CampusVideoBackground
import com.example.campusai.ui.components.CampusAmbientField
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import kotlinx.coroutines.launch

private val LoginInk = Color(0xFF111A31)
private val LoginBlue = Color(0xFF596AF0)
private val LoginBlueDeep = Color(0xFF3E50D9)
private val LoginWarm = Color(0xFFFFA45B)
private val FormText = Color(0xFFF8FAFF)
private val FormMuted = Color(0xBDEBF0FF)

@Composable
fun LoginScreen(repository: AppRepository, onLoginSuccess: () -> Unit) {
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var rememberMe by remember { mutableStateOf(true) }
    LaunchedEffect(Unit) {
        repository.savedUsername()?.takeIf { it.isNotBlank() }?.let { username = it }
    }

    fun submit() {
        if (loading) return
        focusManager.clearFocus()
        if (username.isBlank() || password.isBlank()) {
            error = if (username.isBlank()) "请输入学号、工号或用户名。" else "请输入密码后继续。"
            return
        }
        scope.launch {
            loading = true
            error = ""
            try {
                repository.login(username.trim(), password, rememberCredentials = rememberMe)
                onLoginSuccess()
            } catch (e: Exception) {
                error = e.message ?: "暂时无法登录，请检查网络后重试。"
            } finally {
                loading = false
            }
        }
    }

    Box(Modifier.fillMaxSize().background(LoginInk)) {
        CampusVideoBackground(
            videoRes = R.raw.login_campus,
            posterRes = R.drawable.campus_login_poster,
            motionEnabled = !reduceMotion,
            modifier = Modifier.fillMaxSize(),
        )
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(
                    0f to Color(0x5C091632),
                    .38f to Color(0x52091632),
                    .68f to Color(0xC4091632),
                    1f to Color(0xF0091632),
                ),
            ),
        )
        CampusAmbientField(
            modifier = Modifier.fillMaxSize(),
            darkMode = true,
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
                .imePadding()
                .verticalScroll(rememberScrollState()),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 24.dp, top = 20.dp, end = 24.dp)
                    .enterAnimation(delayMs = 30, enabled = !reduceMotion),
            ) {
                LoginBrand()
                Spacer(Modifier.height(66.dp))
                Text(
                    "欢迎回到校园",
                    color = Color.White,
                    fontSize = 32.sp,
                    lineHeight = 38.sp,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = (-.5).sp,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "课程、通知与每一个重要截止，\n都替你稳稳记着。",
                    color = Color.White.copy(alpha = .82f),
                    fontSize = 13.sp,
                    lineHeight = 20.sp,
                )
            }

            Spacer(Modifier.height(42.dp))
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 24.dp, top = 18.dp, end = 24.dp, bottom = 24.dp)
                    .enterAnimation(delayMs = 130, enabled = !reduceMotion),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Text("登录 CampusMate", color = FormText, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                Text(
                    "使用学校统一身份账号继续。",
                    color = FormMuted,
                    fontSize = 11.5.sp,
                )

                LoginField(
                    label = "账号",
                    value = username,
                    placeholder = "学号 / 工号 / 用户名",
                    icon = { Icon(Icons.Default.Person, null, tint = FormMuted, modifier = Modifier.size(18.dp)) },
                    onValueChange = { username = it; error = "" },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                    keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) }),
                )
                LoginField(
                    label = "密码",
                    value = password,
                    placeholder = "请输入密码",
                    icon = { Icon(Icons.Default.Lock, null, tint = FormMuted, modifier = Modifier.size(18.dp)) },
                    trailing = {
                        Icon(
                            if (showPassword) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                            if (showPassword) "隐藏密码" else "显示密码",
                            tint = FormMuted,
                            modifier = Modifier.size(20.dp).campusClickable { showPassword = !showPassword },
                        )
                    },
                    onValueChange = { password = it; error = "" },
                    visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                )

                AnimatedContent(
                    targetState = error,
                    transitionSpec = { fadeIn() togetherWith fadeOut() using SizeTransform(clip = false) },
                    label = "login-error",
                ) { message ->
                    if (message.isNotEmpty()) {
                        Text(
                            message,
                            color = Color(0xFFFFC5BF),
                            fontSize = 11.5.sp,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(Color(0x663E171A), RoundedCornerShape(10.dp))
                                .padding(horizontal = 12.dp, vertical = 9.dp),
                        )
                    }
                }

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 48.dp)
                        .toggleable(
                            value = rememberMe,
                            role = Role.Checkbox,
                            onValueChange = { rememberMe = it },
                        ),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(
                        checked = rememberMe,
                        onCheckedChange = null,
                        colors = CheckboxDefaults.colors(
                            checkedColor = LoginBlue,
                            uncheckedColor = FormMuted,
                            checkmarkColor = Color.White,
                        ),
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        "记住账号密码（下次自动登录）",
                        color = FormMuted,
                        fontSize = 12.sp,
                    )
                }

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(51.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(Color.White)
                        .campusClickable(enabled = !loading) { submit() },
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center,
                ) {
                    if (loading) {
                        CircularProgressIndicator(color = LoginBlueDeep, strokeWidth = 2.dp, modifier = Modifier.size(18.dp))
                    } else {
                        Text("进入校园空间", color = LoginBlueDeep, fontSize = 14.sp, fontWeight = FontWeight.Bold)
                        Spacer(Modifier.size(8.dp))
                        Icon(Icons.Default.ArrowForward, null, tint = LoginBlueDeep, modifier = Modifier.size(17.dp))
                    }
                }

                Text(
                    "登录即表示你已阅读并同意校园数据使用说明",
                    color = Color.White.copy(alpha = .48f),
                    fontSize = 9.5.sp,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
            }
        }
    }
}

@Composable
private fun LoginBrand() {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.size(40.dp).clip(RoundedCornerShape(13.dp)).background(LoginWarm),
            contentAlignment = Alignment.Center,
        ) {
            Icon(Icons.Default.School, null, tint = Color.White, modifier = Modifier.size(23.dp))
        }
        Spacer(Modifier.width(10.dp))
        Column {
            Text("CampusMate AI", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.Bold)
            Text("校园事务 · 温和陪伴", color = Color.White.copy(alpha = .7f), fontSize = 9.5.sp)
        }
    }
}

@Composable
private fun LoginField(
    label: String,
    value: String,
    placeholder: String,
    icon: @Composable () -> Unit,
    trailing: (@Composable () -> Unit)? = null,
    onValueChange: (String) -> Unit,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    keyboardActions: KeyboardActions = KeyboardActions.Default,
) {
    var focused by remember { mutableStateOf(false) }
    val underlineColor by animateColorAsState(
        targetValue = if (focused) Color.White else Color.White.copy(alpha = .32f),
        label = "login-field-line",
    )
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, color = FormMuted, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = true,
            textStyle = TextStyle(color = FormText, fontSize = 14.sp),
            cursorBrush = SolidColor(Color.White),
            visualTransformation = visualTransformation,
            keyboardOptions = keyboardOptions,
            keyboardActions = keyboardActions,
            modifier = Modifier.fillMaxWidth().onFocusChanged { focused = it.isFocused },
            decorationBox = { input ->
                Column {
                    Row(
                        modifier = Modifier.fillMaxWidth().height(45.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(11.dp),
                    ) {
                        icon()
                        Box(Modifier.weight(1f)) {
                            if (value.isEmpty()) {
                                Text(placeholder, color = Color.White.copy(alpha = .46f), fontSize = 13.sp)
                            }
                            input()
                        }
                        trailing?.invoke()
                    }
                    Box(Modifier.fillMaxWidth().height(1.dp).background(underlineColor))
                }
            },
        )
    }
}

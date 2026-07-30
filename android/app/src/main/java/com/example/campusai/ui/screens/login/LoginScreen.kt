package com.example.campusai.ui.screens.login

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(
    repository: AppRepository,
    onLoginSuccess: () -> Unit
) {
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    var username by remember { mutableStateOf("student_demo") }
    var password by remember { mutableStateOf("Demo123456") }
    var showPassword by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val mockMode by repository.mockMode.collectAsState()

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(durationMillis = 650, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(LoginBg)
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.horizontalGradient(
                        colors = listOf(
                            Color(0x7A020C19),
                            Color(0xBA020C19),
                            Color(0xE0020C19)
                        )
                    )
                )
        )

        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 40.dp, vertical = 58.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier
                    .weight(1.2f)
                    .graphicsLayer { alpha = animatedAlpha; translationY = 16f * (1f - animatedAlpha) },
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                BrandRow(light = true)
                Spacer(Modifier.height(24.dp))
                Column {
                    Text(
                        "你的校园事务工作台",
                        color = Color(0xFFC3D5E1),
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.08.sp
                    )
                    Spacer(Modifier.height(12.dp))
                    Text(
                        "把今天的校园生活\n理清楚。",
                        color = Color.White,
                        fontSize = 42.sp,
                        lineHeight = 47.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = (-0.04).sp
                    )
                    Spacer(Modifier.height(18.dp))
                    Text(
                        "通知、课程、任务和 AI 导员，都在一个清晰的入口。",
                        color = Color(0xFFC3D5E1),
                        fontSize = 17.sp
                    )
                }
                Spacer(Modifier.height(24.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(38.dp)) {
                    FeatureTag("通知智能整理")
                    FeatureTag("任务协同管理")
                    FeatureTag("AI 导员陪伴")
                }
            }

            Column(
                modifier = Modifier
                    .width(430.dp)
                    .graphicsLayer { alpha = animatedAlpha; translationY = 16f * (1f - animatedAlpha) }
                    .clip(RoundedCornerShape(14.dp))
                    .background(LoginPanelBg)
                    .padding(34.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(18.dp)
            ) {
                Column {
                    Text(
                        "欢迎回来",
                        color = Muted,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 0.08.sp
                    )
                    Spacer(Modifier.height(5.dp))
                    Text(
                        "账号登录",
                        color = TextPrimary,
                        fontSize = 27.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "使用学号、工号或管理员账号登录",
                        color = Muted,
                        fontSize = 13.sp
                    )
                }

                OutlinedTextField(
                    value = username,
                    onValueChange = { username = it },
                    label = { Text("账号") },
                    placeholder = { Text("请输入学号 / 工号 / 用户名") },
                    leadingIcon = { Icon(Icons.Default.Person, null, tint = Muted) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(9.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = InputBorder,
                        focusedContainerColor = Color.White,
                        unfocusedContainerColor = Color.White
                    ),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                    keyboardActions = KeyboardActions(onNext = { focusManager.moveFocus(FocusDirection.Down) })
                )

                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("密码") },
                    placeholder = { Text("请输入密码") },
                    leadingIcon = { Icon(Icons.Default.Lock, null, tint = Muted) },
                    trailingIcon = {
                        IconButton(onClick = { showPassword = !showPassword }) {
                            Icon(
                                if (showPassword) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                                if (showPassword) "隐藏密码" else "显示密码",
                                tint = Muted
                            )
                        }
                    },
                    visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(9.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Primary,
                        unfocusedBorderColor = InputBorder,
                        focusedContainerColor = Color.White,
                        unfocusedContainerColor = Color.White
                    ),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = {
                        focusManager.clearFocus()
                        scope.launch {
                            loading = true; error = ""
                            try { repository.login(username.trim(), password); onLoginSuccess() }
                            catch (e: Exception) { error = e.message ?: "登录失败，请稍后重试" }
                            finally { loading = false }
                        }
                    })
                )

                if (error.isNotEmpty()) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(AlertErrorBg)
                            .padding(10.dp, 12.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(Icons.Default.Warning, null, tint = AlertErrorText, modifier = Modifier.size(16.dp))
                        Text(error, color = AlertErrorText, fontSize = 13.sp)
                    }
                }

                Button(
                    onClick = {
                        scope.launch {
                            loading = true; error = ""
                            try { repository.login(username.trim(), password); onLoginSuccess() }
                            catch (e: Exception) { error = e.message ?: "登录失败，请稍后重试" }
                            finally { loading = false }
                        }
                    },
                    enabled = !loading,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary, disabledContainerColor = Primary.copy(alpha = 0.55f))
                ) {
                    Text(if (loading) "正在登录…" else "登录", fontWeight = FontWeight.SemiBold)
                    if (!loading) Icon(Icons.Default.ArrowForward, null, modifier = Modifier.size(18.dp))
                }

                Spacer(Modifier.height(4.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("演示账号", color = Muted, fontSize = 12.sp)
                    DemoButton("学生") { username = "student_demo"; password = "Demo123456" }
                    DemoButton("教师") { username = "teacher_demo"; password = "Demo123456" }
                    DemoButton("管理员") { username = "admin_demo"; password = "Demo123456" }
                }

                Row(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(Modifier.size(6.dp).clip(CircleShape).background(Accent))
                    Text(
                        if (mockMode) "当前为 Mock 演示模式" else "将连接真实后端",
                        color = Muted, fontSize = 11.sp
                    )
                }
            }
        }
    }
}

@Composable
private fun BrandRow(light: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(
            modifier = Modifier
                .size(42.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(Color(0xFF2675AA)),
            contentAlignment = Alignment.Center
        ) {
            Icon(Icons.Default.School, null, tint = Color.White, modifier = Modifier.size(24.dp))
        }
        Column {
            Text("CampusMate AI", color = Color.White, fontSize = 16.sp, fontWeight = FontWeight.Bold)
            Text(
                "校园信息中枢",
                color = if (light) Color(0xFFB8CEDE) else Color(0xFF6F8290),
                fontSize = 11.sp
            )
        }
    }
}

@Composable
private fun FeatureTag(text: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(9.dp)) {
        Text(text, color = Color(0xFFDCE9F0), fontSize = 14.sp)
    }
}

@Composable
private fun DemoButton(label: String, onClick: () -> Unit) {
    OutlinedButton(
        onClick = onClick,
        shape = RoundedCornerShape(6.dp),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),

        colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary)
    ) {
        Text(label, fontSize = 12.sp)
    }
}


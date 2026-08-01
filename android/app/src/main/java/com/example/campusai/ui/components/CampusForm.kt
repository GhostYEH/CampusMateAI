package com.example.campusai.ui.components

import android.annotation.SuppressLint
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.InputBorder
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** 表单字段标签 + 内容容器。 */
@Composable
fun FormField(
    label: String,
    modifier: Modifier = Modifier,
    error: String? = null,
    content: @Composable () -> Unit,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        Text(label, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(7.dp))
        content()
        if (error != null) {
            Spacer(Modifier.height(5.dp))
            Text(error, color = DangerText, fontSize = 11.sp)
        }
    }
}

/** 统一风格的文本输入框。 */
@Composable
fun CampusTextField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
    minLines: Int = 1,
    keyboardType: KeyboardType = KeyboardType.Text,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Surface)
            .border(1.dp, InputBorder, RoundedCornerShape(12.dp))
            .padding(horizontal = 13.dp, vertical = if (minLines > 1) 12.dp else 0.dp),
        contentAlignment = if (minLines > 1) Alignment.TopStart else Alignment.CenterStart,
    ) {
        if (value.isEmpty()) {
            Text(placeholder, color = Muted, fontSize = 13.sp)
        }
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            textStyle = TextStyle(color = TextPrimary, fontSize = 13.sp),
            cursorBrush = SolidColor(Primary),
            keyboardOptions = KeyboardOptions(keyboardType = keyboardType),
            minLines = minLines,
            modifier = Modifier
                .fillMaxWidth()
                .then(if (minLines > 1) Modifier else Modifier.height(44.dp)),
        )
    }
}

/** 下拉选择（占位文本 + 弹层选项）。 */
@Composable
fun FormDropdown(
    options: List<String>,
    selected: String?,
    onSelect: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(Surface)
                .border(1.dp, InputBorder, RoundedCornerShape(12.dp))
                .campusClickable { expanded = true }
                .padding(horizontal = 13.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                selected ?: placeholder,
                color = if (selected == null) Muted else TextPrimary,
                fontSize = 13.sp,
                modifier = Modifier.weight(1f),
            )
            Icon(Icons.Default.ArrowDropDown, null, tint = Muted, modifier = Modifier.size(20.dp))
        }
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.background(Surface),
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = {
                        Text(
                            option,
                            color = if (option == selected) Primary else TextPrimary,
                            fontSize = 13.sp,
                            fontWeight = if (option == selected) FontWeight.SemiBold else FontWeight.Normal,
                        )
                    },
                    onClick = {
                        onSelect(option)
                        expanded = false
                    },
                )
            }
        }
    }
}

/** 开关行。 */
@Composable
fun FormSwitchRow(
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(12.dp))
            .padding(horizontal = 13.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Text(subtitle, color = Muted, fontSize = 11.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedTrackColor = Primary,
                checkedThumbColor = Surface,
                uncheckedTrackColor = PrimarySoft,
                uncheckedBorderColor = Line,
            ),
        )
    }
}

/** 图片选择与预览入口（仅本地选择，不上传）。 */
@Composable
@SuppressLint("ProduceStateDoesNotAssignValue")
fun ImagePickField(
    imageUri: String?,
    onPick: (String?) -> Unit,
    hint: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        onPick(uri?.toString())
    }
    var bitmap by remember(imageUri) { mutableStateOf<ImageBitmap?>(null) }
    LaunchedEffect(imageUri) {
        bitmap = if (imageUri != null) {
            withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.openInputStream(Uri.parse(imageUri))?.use { input ->
                        BitmapFactory.decodeStream(input)?.asImageBitmap()
                    }
                }.getOrNull()
            }
        } else null
    }
    Column(modifier = modifier.fillMaxWidth()) {
        if (bitmap != null) {
            Box {
                Image(
                    bitmap = bitmap!!,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(150.dp)
                        .clip(RoundedCornerShape(12.dp)),
                )
                Box(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(8.dp)
                        .clip(CircleShape)
                        .background(PrimarySoft)
                        .campusClickable { onPick(null) }
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                ) {
                    Text("移除", color = Primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        } else {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(Surface)
                    .border(1.dp, InputBorder, RoundedCornerShape(12.dp))
                    .campusClickable { launcher.launch("image/*") }
                    .padding(horizontal = 13.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(Icons.Default.AddPhotoAlternate, null, tint = Primary, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(hint, color = Muted, fontSize = 12.sp)
            }
        }
    }
}

/** 附件选择入口（任意文件，仅记录文件名）。 */
@Composable
fun AttachmentPickField(
    fileName: String?,
    onPick: (String?, String?) -> Unit,
    hint: String,
    modifier: Modifier = Modifier,
) {
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri: Uri? ->
        onPick(uri?.toString(), uri?.lastPathSegment)
    }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Surface)
            .border(1.dp, InputBorder, RoundedCornerShape(12.dp))
            .campusClickable { launcher.launch("*/*") }
            .padding(horizontal = 13.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.AttachFile, null, tint = Primary, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text(
            fileName ?: hint,
            color = if (fileName == null) Muted else TextPrimary,
            fontSize = 12.sp,
            maxLines = 1,
        )
    }
}

/** 主按钮（统一高度 46dp）。 */
@Composable
fun CampusPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .height(46.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(if (enabled) Primary else PrimarySoft)
            .campusClickable(enabled = enabled, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = if (enabled) MaterialTheme.colorScheme.onPrimary else Muted,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

// ── 日期 / 时间选项生成（避免引入实验性 DatePicker，保证小屏可用） ──

object DateTimeOptions {
    private val DATE_LABEL: DateTimeFormatter = DateTimeFormatter.ofPattern("M月d日 EEEE")
    private val DATE_TIME_LABEL: DateTimeFormatter = DateTimeFormatter.ofPattern("M月d日 HH:mm")

    /** 未来 [days] 天的日期，label 如 "8月1日 周五"，value 为 ISO。 */
    fun dates(days: Int = 60, from: LocalDate = LocalDate.now()): List<Pair<String, String>> =
        (0L until days).map { offset ->
            val date = from.plusDays(offset)
            date.format(DATE_LABEL) to date.toString()
        }

    /** 每日 07:00 - 22:00，30 分钟步长的时间点。 */
    fun times(): List<String> = (7 * 60..22 * 60 step 30).map { minutes ->
        "%02d:%02d".format(minutes / 60, minutes % 60)
    }

    /** 未来 [days] 天的日期时间（小时粒度），label 如 "8月1日 14:00"。 */
    fun dateTimes(days: Int = 30, from: LocalDateTime = LocalDate.now().atTime(8, 0)): List<Pair<String, String>> =
        (0L until days * 12).map { step ->
            val dt = from.plusDays(step / 12).plusHours((step % 12))
            dt.format(DATE_TIME_LABEL) to dt.format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm"))
        }
}

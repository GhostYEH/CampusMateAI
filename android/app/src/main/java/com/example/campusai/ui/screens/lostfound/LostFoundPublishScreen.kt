package com.example.campusai.ui.screens.lostfound

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.LostFoundForm
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.data.repository.LostFoundRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.DateTimeOptions
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.components.FormSwitchRow
import com.example.campusai.ui.components.ImagePickField
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun LostFoundPublishScreen(
    repository: LostFoundRepository,
    appRepository: AppRepository,
    onBack: () -> Unit,
    onPublished: (Long) -> Unit,
) {
    val session by appRepository.session.collectAsState()
    val scope = rememberCoroutineScope()
    val categoryOptions = CampusStrings.LostFound.CATEGORIES.split(",")
    val locationOptions = CampusStrings.LostFound.LOCATIONS.split(",")
    val timeOptions = remember { DateTimeOptions.dateTimes(14) }

    var kind by remember { mutableStateOf(LostFoundKind.LOST) }
    var title by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var time by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }
    var contact by remember { mutableStateOf("") }
    var imageUri by remember { mutableStateOf<String?>(null) }
    var anonymous by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var publishing by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.LostFound.PUBLISH_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))
        CampusCard {
            FormField(label = "信息类型") {
                FilterChipRow(
                    options = listOf(CampusStrings.LostFound.KIND_LOST, CampusStrings.LostFound.KIND_FOUND),
                    selected = if (kind == LostFoundKind.LOST) CampusStrings.LostFound.KIND_LOST else CampusStrings.LostFound.KIND_FOUND,
                    onSelect = { kind = if (it == CampusStrings.LostFound.KIND_LOST) LostFoundKind.LOST else LostFoundKind.FOUND },
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_TITLE) {
                CampusTextField(
                    value = title,
                    onValueChange = { title = it },
                    placeholder = CampusStrings.LostFound.FIELD_TITLE_HINT,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_CATEGORY) {
                FilterChipRow(options = categoryOptions, selected = category, onSelect = { category = it })
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_DESC) {
                CampusTextField(
                    value = description,
                    onValueChange = { description = it },
                    placeholder = CampusStrings.LostFound.FIELD_DESC_HINT,
                    minLines = 3,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_TIME) {
                FormDropdown(
                    options = timeOptions.map { it.first },
                    selected = timeOptions.firstOrNull { it.second == time }?.first,
                    onSelect = { label -> time = timeOptions.first { it.first == label }.second },
                    placeholder = "请选择大致时间",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_LOCATION) {
                FormDropdown(
                    options = locationOptions,
                    selected = location.ifBlank { null },
                    onSelect = { location = it },
                    placeholder = "请选择地点",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_IMAGE) {
                ImagePickField(
                    imageUri = imageUri,
                    onPick = { imageUri = it },
                    hint = CampusStrings.LostFound.FIELD_IMAGE_HINT,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.LostFound.FIELD_CONTACT) {
                CampusTextField(
                    value = contact,
                    onValueChange = { contact = it },
                    placeholder = "手机号 / 微信 / 邮箱",
                )
            }
        }
        Spacer(Modifier.height(12.dp))
        FormSwitchRow(
            title = CampusStrings.LostFound.FIELD_ANONYMOUS,
            subtitle = if (anonymous) CampusStrings.LostFound.ANONYMOUS_ON else CampusStrings.LostFound.ANONYMOUS_OFF,
            checked = anonymous,
            onCheckedChange = { anonymous = it },
        )
        if (error != null) {
            Spacer(Modifier.height(10.dp))
            Text(error.orEmpty(), color = DangerText, fontSize = 12.sp)
        }
        Spacer(Modifier.height(18.dp))
        CampusPrimaryButton(
            text = CampusStrings.LostFound.PUBLISH,
            enabled = !publishing,
            onClick = {
                val form = LostFoundForm(
                    kind = kind,
                    title = title,
                    category = category,
                    description = description,
                    time = time.ifBlank { "" }.let { raw ->
                        timeOptions.firstOrNull { it.second == raw }?.first ?: raw
                    },
                    location = location,
                    contact = contact,
                    anonymous = anonymous,
                    imageUri = imageUri,
                )
                val validation = form.validate()
                if (validation != null) {
                    error = validation
                    return@CampusPrimaryButton
                }
                error = null
                publishing = true
                scope.launch {
                    val result = repository.publish(form, session?.name ?: "匿名同学")
                    publishing = false
                    result.onSuccess { onPublished(it) }
                        .onFailure { error = it.message }
                }
            },
        )
        Spacer(Modifier.height(120.dp))
    }
}

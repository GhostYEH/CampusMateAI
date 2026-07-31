package com.example.campusai.ui.screens.services

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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.RepairForm
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.FormField
import com.example.campusai.ui.components.ImagePickField
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import kotlinx.coroutines.launch

@Composable
fun RepairRequestScreen(
    repository: ServiceRepository,
    onBack: () -> Unit,
    onSubmitted: (Long) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val buildingOptions = CampusStrings.Services.REPAIR_BUILDINGS.split(",")
    val typeOptions = CampusStrings.Services.REPAIR_TYPES.split(",")
    val urgencyOptions = CampusStrings.Services.REPAIR_URGENCIES.split(",")

    var building by remember { mutableStateOf("") }
    var room by remember { mutableStateOf("") }
    var type by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var imageUri by remember { mutableStateOf<String?>(null) }
    var urgency by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var showConfirm by remember { mutableStateOf(false) }
    var submitting by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.Services.REPAIR_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))
        CampusCard {
            FormField(label = CampusStrings.Services.REPAIR_BUILDING) {
                FormDropdown(
                    options = buildingOptions,
                    selected = building.ifBlank { null },
                    onSelect = { building = it },
                    placeholder = "请选择宿舍楼",
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.REPAIR_ROOM) {
                CampusTextField(
                    value = room,
                    onValueChange = { room = it },
                    placeholder = "例如：412",
                    keyboardType = KeyboardType.Number,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.REPAIR_TYPE) {
                FilterChipRow(options = typeOptions, selected = type, onSelect = { type = it })
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.REPAIR_DESC) {
                CampusTextField(
                    value = description,
                    onValueChange = { description = it },
                    placeholder = CampusStrings.Services.REPAIR_DESC_HINT,
                    minLines = 3,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = "${CampusStrings.Services.REPAIR_IMAGE}（${CampusStrings.Common.OPTIONAL}）") {
                ImagePickField(
                    imageUri = imageUri,
                    onPick = { imageUri = it },
                    hint = CampusStrings.Services.REPAIR_IMAGE_HINT,
                )
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.REPAIR_URGENCY) {
                FilterChipRow(options = urgencyOptions, selected = urgency, onSelect = { urgency = it })
            }
            Spacer(Modifier.height(14.dp))
            FormField(label = CampusStrings.Services.REPAIR_PHONE) {
                CampusTextField(
                    value = phone,
                    onValueChange = { phone = it.filter(Char::isDigit).take(11) },
                    placeholder = CampusStrings.Services.LEAVE_PHONE_HINT,
                    keyboardType = KeyboardType.Phone,
                )
            }
        }
        if (error != null) {
            Spacer(Modifier.height(10.dp))
            Text(error.orEmpty(), color = DangerText, fontSize = 12.sp)
        }
        Spacer(Modifier.height(18.dp))
        CampusPrimaryButton(
            text = CampusStrings.Common.SUBMIT,
            enabled = !submitting,
            onClick = {
                val form = RepairForm(building, room, type, description, imageUri, urgency, phone)
                val validation = form.validate()
                if (validation != null) {
                    error = validation
                } else {
                    error = null
                    showConfirm = true
                }
            },
        )
        Spacer(Modifier.height(120.dp))
    }

    if (showConfirm) {
        ConfirmDialog(
            title = CampusStrings.Services.REPAIR_TITLE,
            message = CampusStrings.Services.REPAIR_SUBMIT_CONFIRM,
            confirmText = CampusStrings.Common.SUBMIT,
            onConfirm = {
                showConfirm = false
                submitting = true
                scope.launch {
                    val result = repository.submitRepair(
                        RepairForm(building, room, type, description, imageUri, urgency, phone),
                    )
                    submitting = false
                    result.onSuccess { onSubmitted(it) }
                        .onFailure { error = it.message }
                }
            },
            onDismiss = { showConfirm = false },
        )
    }
}

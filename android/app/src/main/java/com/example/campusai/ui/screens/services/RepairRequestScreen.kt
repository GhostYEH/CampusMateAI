package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Apartment
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.Phone
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
import com.example.campusai.R
import com.example.campusai.data.model.RepairForm
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.ImagePickField
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
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
    var building by remember { mutableStateOf("") }
    var room by remember { mutableStateOf("") }
    var type by remember { mutableStateOf("水电维修") }
    var description by remember { mutableStateOf("") }
    var imageUri by remember { mutableStateOf<String?>(null) }
    var urgency by remember { mutableStateOf("一般") }
    var phone by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var showConfirm by remember { mutableStateOf(false) }
    var submitting by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize().background(Background).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp)) {
        ServiceHeroHeader("宿舍报修", "快速提交宿舍维修问题，工作人员将尽快处理", R.drawable.service_repair_hero, onBack)
        ServiceFormCard {
            ServiceSection("宿舍楼") { ServiceSelectField(listOf("竹园 1 栋", "竹园 2 栋", "竹园 3 栋", "松园 1 栋"), building, "请选择宿舍楼", Icons.Default.Apartment) { building = it } }
            ServiceSection("房间号") { ServiceInput(room, { room = it.take(8) }, "例如：412", Icons.Default.MeetingRoom, KeyboardType.Number) }
            ServiceSection("报修类型") { ServiceOptionRow(listOf("水电维修", "家具门窗", "网络故障", "空调卫浴", "其他"), type) { type = it } }
            ServiceSection("问题描述") { ServiceInput(description, { description = it }, "请描述具体问题（至少 10 个字）", Icons.Default.Edit, lines = 4, maxLength = 200) }
            ServiceSection("现场照片（选填）") { ImagePickField(imageUri, { imageUri = it }, "点击上传现场照片，帮助我们更快定位问题（最多 6 张）") }
            ServiceSection("紧急程度") { ServiceOptionRow(listOf("一般", "较急", "非常紧急"), urgency) { urgency = it } }
            ServiceSection("联系电话") { ServiceInput(phone, { phone = it.filter(Char::isDigit).take(11) }, "11 位手机号", Icons.Default.Phone, KeyboardType.Phone) }
        }
        if (error != null) Text(error.orEmpty(), color = DangerText, fontSize = 12.sp, modifier = Modifier.padding(top = 10.dp, start = 8.dp))
        Spacer(Modifier.height(17.dp))
        ServiceNotice("提交后，维修人员通常会在 24 小时内与您联系，请保持电话畅通。")
        Spacer(Modifier.height(14.dp))
        ServiceSubmitButton("提交报修", !submitting) {
            val form = RepairForm(building, room, type, description, imageUri, urgency, phone)
            error = form.validate(); if (error == null) showConfirm = true
        }
        Spacer(Modifier.height(BottomDockReservedHeight + 20.dp))
    }
    if (showConfirm) ConfirmDialog(
        title = "宿舍报修", message = "确认提交报修申请吗？", confirmText = "提交报修",
        onConfirm = {
            showConfirm = false; submitting = true
            scope.launch {
                repository.submitRepair(RepairForm(building, room, type, description, imageUri, urgency, phone))
                    .onSuccess { onSubmitted(it) }.onFailure { error = it.message }
                submitting = false
            }
        }, onDismiss = { showConfirm = false },
    )
}

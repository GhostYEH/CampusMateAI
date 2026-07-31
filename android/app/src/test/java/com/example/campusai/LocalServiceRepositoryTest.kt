package com.example.campusai

import com.example.campusai.data.local.InMemoryKeyValueStorage
import com.example.campusai.data.model.LeaveForm
import com.example.campusai.data.model.RepairForm
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.repository.LocalServiceRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalServiceRepositoryTest {

    private fun newRepo(storage: InMemoryKeyValueStorage = InMemoryKeyValueStorage()) =
        LocalServiceRepository(storage = storage)

    private fun validLeave() = LeaveForm(
        type = "病假",
        startAt = "2026-08-02T08:00",
        endAt = "2026-08-03T18:00",
        reason = "感冒发烧到校医院就诊，医嘱建议休息两天。",
        phone = "13800002026",
        attachmentUri = null,
    )

    private fun validRepair() = RepairForm(
        building = "竹园 3 栋",
        room = "412",
        type = "水电维修",
        description = "宿舍洗手池水龙头持续滴水，关闭后仍有渗漏。",
        imageUri = null,
        urgency = "一般",
        phone = "13800002026",
    )

    @Test
    fun `请假表单校验`() {
        assertNotNull(validLeave().copy(endAt = "2026-08-01T18:00").validate()) // 结束早于开始
        assertNotNull(validLeave().copy(reason = "短").validate())
        assertNotNull(validLeave().copy(phone = "123").validate())
        assertNull(validLeave().validate())
    }

    @Test
    fun `报修表单校验`() {
        assertNotNull(validRepair().copy(room = "").validate())
        assertNotNull(validRepair().copy(description = "太短").validate())
        assertNull(validRepair().validate())
    }

    @Test
    fun `提交请假生成审核中申请与时间线`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val before = repo.requests.value.size
        val id = repo.submitLeave(validLeave()).getOrThrow()

        assertEquals(before + 1, repo.requests.value.size)
        val request = repo.getById(id)
        assertNotNull(request)
        assertEquals(RequestStatus.PENDING, request?.status)
        assertEquals(ServiceKind.LEAVE, request?.kind)
        assertTrue((request?.timeline?.size ?: 0) >= 2)
        assertEquals("病假", request?.fields?.get("请假类型"))
    }

    @Test
    fun `提交报修生成申请`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val id = repo.submitRepair(validRepair()).getOrThrow()
        val request = repo.getById(id)
        assertEquals(ServiceKind.REPAIR, request?.kind)
        assertEquals(RequestStatus.PENDING, request?.status)
    }

    @Test
    fun `通用事项提交与标题校验`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        assertTrue(repo.submitGeneric(ServiceKind.FEEDBACK, "", emptyMap()).isFailure)
        val id = repo.submitGeneric(
            ServiceKind.CERTIFICATE,
            "在读证明申请",
            mapOf("用途" to "签证办理"),
        ).getOrThrow()
        assertNotNull(repo.getById(id))
    }

    @Test
    fun `种子数据包含多种状态`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val statuses = repo.requests.value.map { it.status }.toSet()
        assertTrue(statuses.contains(RequestStatus.APPROVED))
        assertTrue(statuses.contains(RequestStatus.REJECTED))
        assertTrue(statuses.contains(RequestStatus.COMPLETED))
    }

    @Test
    fun `提交数据在重建仓库后保持`() = runBlocking {
        val storage = InMemoryKeyValueStorage()
        val repo = newRepo(storage)
        repo.refresh()
        val id = repo.submitLeave(validLeave()).getOrThrow()

        val restored = newRepo(storage)
        restored.refresh()
        assertNotNull(restored.getById(id))
    }
}

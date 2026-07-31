package com.example.campusai

import com.example.campusai.data.local.InMemoryKeyValueStorage
import com.example.campusai.data.model.LostFoundForm
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.model.LostFoundStatus
import com.example.campusai.data.repository.LocalLostFoundRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalLostFoundRepositoryTest {

    private fun newRepo(storage: InMemoryKeyValueStorage = InMemoryKeyValueStorage()) =
        LocalLostFoundRepository(storage = storage)

    private fun validForm() = LostFoundForm(
        kind = LostFoundKind.LOST,
        title = "蓝色水杯",
        category = "生活用品",
        description = "膳魔师蓝色保温杯，杯底刻有一个小星星。",
        time = "今天 10:00",
        location = "图书馆",
        contact = "13800002026",
        anonymous = false,
        imageUri = null,
    )

    @Test
    fun `首次加载包含演示数据`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        assertTrue(repo.items.value.isNotEmpty())
        assertTrue(repo.items.value.any { it.kind == LostFoundKind.LOST })
        assertTrue(repo.items.value.any { it.kind == LostFoundKind.FOUND })
    }

    @Test
    fun `发布校验拦截非法表单`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val bad = repo.publish(validForm().copy(title = "a"), "测试者")
        assertTrue(bad.isFailure)

        val noContact = repo.publish(validForm().copy(contact = ""), "测试者")
        assertTrue(noContact.isFailure)

        val anonymousOk = repo.publish(validForm().copy(contact = "", anonymous = true), "测试者")
        assertTrue(anonymousOk.isSuccess)
    }

    @Test
    fun `发布成功后可查询且归属发布者`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val id = repo.publish(validForm(), "林知夏").getOrThrow()
        val item = repo.getById(id)
        assertNotNull(item)
        assertEquals(true, item?.mine)
        assertEquals(LostFoundStatus.OPEN, item?.status)
    }

    @Test
    fun `标记已找到与删除`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val id = repo.publish(validForm(), "林知夏").getOrThrow()

        repo.close(id)
        assertEquals(LostFoundStatus.CLOSED, repo.getById(id)?.status)

        repo.delete(id)
        assertNull(repo.getById(id))
    }

    @Test
    fun `筛选与排序纯函数`() = runBlocking {
        val repo = newRepo()
        repo.refresh()
        val items = repo.items.value

        val lostOnly = LocalLostFoundRepository.filter(
            items, LostFoundKind.LOST, "", "全部", "全部", true,
        )
        assertTrue(lostOnly.all { it.kind == LostFoundKind.LOST })

        val searched = LocalLostFoundRepository.filter(
            items, LostFoundKind.LOST, "充电宝", "全部", "全部", true,
        )
        assertTrue(searched.isNotEmpty())
        assertTrue(searched.all { it.title.contains("充电宝") || it.description.contains("充电宝") })

        val byCategory = LocalLostFoundRepository.filter(
            items, LostFoundKind.FOUND, "", "电子产品", "全部", true,
        )
        assertTrue(byCategory.all { it.category == "电子产品" })

        val newest = LocalLostFoundRepository.filter(items, LostFoundKind.LOST, "", "全部", "全部", true)
        val oldest = LocalLostFoundRepository.filter(items, LostFoundKind.LOST, "", "全部", "全部", false)
        assertEquals(newest.map { it.id }, oldest.reversed().map { it.id })
    }
}

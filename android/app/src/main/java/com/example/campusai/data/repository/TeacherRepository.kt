package com.example.campusai.data.repository

import com.example.campusai.data.local.KeyValueStorage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

data class TeacherDraft(val id: Long, val kind: String, val title: String, val content: String, val savedAt: Long)

class LocalTeacherRepository(private val storage: KeyValueStorage) {
    private val scope = CoroutineScope(Dispatchers.IO)
    private val _drafts = MutableStateFlow<List<TeacherDraft>>(emptyList())
    val drafts: StateFlow<List<TeacherDraft>> = _drafts.asStateFlow()

    init {
        scope.launch {
            storage.observeRaw("teacher_drafts").collect { raw ->
                _drafts.value = raw?.let(::decode) ?: emptyList()
            }
        }
    }

    suspend fun save(kind: String, title: String, content: String) {
        val draft = TeacherDraft(System.currentTimeMillis(), kind, title.trim(), content.trim(), System.currentTimeMillis())
        val next = listOf(draft) + _drafts.value
        _drafts.value = next
        storage.saveRaw("teacher_drafts", encode(next))
    }

    suspend fun delete(id: Long) {
        val next = _drafts.value.filterNot { it.id == id }
        _drafts.value = next
        storage.saveRaw("teacher_drafts", encode(next))
    }

    private fun encode(items: List<TeacherDraft>) = JSONArray().apply {
        items.forEach { item -> put(JSONObject().apply {
            put("id", item.id); put("kind", item.kind); put("title", item.title)
            put("content", item.content); put("savedAt", item.savedAt)
        }) }
    }.toString()

    private fun decode(raw: String): List<TeacherDraft> = runCatching {
        val json = JSONArray(raw)
        List(json.length()) { index -> json.getJSONObject(index).let {
            TeacherDraft(it.optLong("id"), it.optString("kind"), it.optString("title"), it.optString("content"), it.optLong("savedAt"))
        } }
    }.getOrDefault(emptyList())
}

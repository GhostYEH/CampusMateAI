package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.ApiService
import com.example.campusai.data.remote.CategoryMetaDto
import com.example.campusai.data.remote.CommentDto
import com.example.campusai.data.remote.CommentCreateRequest
import com.example.campusai.data.remote.CommunityPostCreateRequest
import com.example.campusai.data.remote.CommunityPostDto
import com.example.campusai.data.remote.CommunityReportRequest
import com.example.campusai.data.remote.UploadImageResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

class CommunityRepository(private val api: ApiService = ApiClient.api) {

    private val _posts = MutableStateFlow<List<CommunityPostDto>>(emptyList())
    val posts: StateFlow<List<CommunityPostDto>> = _posts.asStateFlow()

    private val _loading = MutableStateFlow(false)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _categories = MutableStateFlow<List<CategoryMetaDto>>(emptyList())
    val categories: StateFlow<List<CategoryMetaDto>> = _categories.asStateFlow()

    private val _total = MutableStateFlow(0)
    val total: StateFlow<Int> = _total.asStateFlow()

    private var currentPage = 1
    private var currentQuery: String? = null
    private var currentCategory: String? = null
    private var currentSort: String = "time"
    private val mutex = Mutex()

    suspend fun loadCategories() {
        try {
            val resp = api.listCommunityCategories()
            if (resp.isSuccessful) {
                _categories.value = resp.body()?.get("items") ?: emptyList()
            }
        } catch (_: Exception) {}
    }

    suspend fun refresh(query: String? = null, category: String? = null, sort: String = "time") {
        currentQuery = query; currentCategory = category; currentSort = sort; currentPage = 1
        _loading.value = true; _error.value = null
        try {
            val resp = api.listCommunityPosts(query = query, category = category, sort = sort, page = 1)
            if (resp.isSuccessful) {
                val body = resp.body()!!
                _posts.value = body.items
                _total.value = body.total
            } else {
                _error.value = parseError(resp.code())
            }
        } catch (e: Exception) {
            _error.value = e.message ?: "加载失败"
        } finally {
            _loading.value = false
        }
    }

    suspend fun loadMore() {
        if (_loading.value || _posts.value.size >= _total.value) return
        mutex.withLock {
            currentPage++
            try {
                val resp = api.listCommunityPosts(query = currentQuery, category = currentCategory, sort = currentSort, page = currentPage)
                if (resp.isSuccessful) {
                    val body = resp.body()!!
                    _posts.value = _posts.value + body.items
                    _total.value = body.total
                }
            } catch (_: Exception) {}
        }
    }

    suspend fun publish(request: CommunityPostCreateRequest): Result<CommunityPostDto> {
        return try {
            val resp = api.createCommunityPost(request)
            if (resp.isSuccessful) {
                val post = resp.body()!!
                _posts.value = listOf(post) + _posts.value
                _total.value = _total.value + 1
                Result.success(post)
            } else Result.failure(Exception(parseError(resp.code())))
        } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun getDetail(id: String): Result<CommunityPostDto> {
        return try {
            val resp = api.getCommunityPost(id)
            if (resp.isSuccessful) Result.success(resp.body()!!) else Result.failure(Exception(parseError(resp.code())))
        } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun deletePost(id: String): Boolean {
        return try {
            val resp = api.deleteCommunityPost(id)
            if (resp.isSuccessful) { _posts.value = _posts.value.filter { it.id != id }; true } else false
        } catch (_: Exception) { false }
    }

    private suspend fun toggleLike(id: String, liked: Boolean): CommunityPostDto? {
        return try {
            val resp = if (liked) api.unlikeCommunityPost(id) else api.likeCommunityPost(id)
            if (resp.isSuccessful) {
                val updated = resp.body()!!
                _posts.value = _posts.value.map { if (it.id == id) updated else it }
                updated
            } else null
        } catch (_: Exception) { null }
    }

    suspend fun like(id: String) { _posts.value.find { it.id == id }?.let { toggleLike(id, it.liked) } }

    suspend fun likeWithState(id: String, liked: Boolean): Result<CommunityPostDto> {
        val updated = toggleLike(id, liked)
        return if (updated != null) Result.success(updated) else Result.failure(Exception("操作失败"))
    }

    suspend fun favorite(id: String) {
        val post = _posts.value.find { it.id == id } ?: return
        try {
            val resp = if (post.favorited) api.unfavoriteCommunityPost(id) else api.favoriteCommunityPost(id)
            if (resp.isSuccessful) {
                val updated = resp.body()!!
                _posts.value = _posts.value.map { if (it.id == id) updated else it }
            }
        } catch (_: Exception) {}
    }

    suspend fun favoriteWithState(id: String, favorited: Boolean): Result<CommunityPostDto> {
        return try {
            val resp = if (favorited) api.unfavoriteCommunityPost(id) else api.favoriteCommunityPost(id)
            if (resp.isSuccessful) {
                val updated = resp.body()!!
                _posts.value = _posts.value.map { if (it.id == id) updated else it }
                Result.success(updated)
            } else Result.failure(Exception("操作失败"))
        } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun listComments(id: String): List<CommentDto> {
        return try {
            val resp = api.listCommunityComments(id)
            if (resp.isSuccessful) resp.body()?.items ?: emptyList() else emptyList()
        } catch (_: Exception) { emptyList() }
    }

    suspend fun addComment(id: String, request: CommentCreateRequest): Result<CommentDto> {
        return try {
            val resp = api.createCommunityComment(id, request)
            if (resp.isSuccessful) Result.success(resp.body()!!) else Result.failure(Exception(parseError(resp.code())))
        } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun report(request: CommunityReportRequest): Boolean {
        return try { api.reportCommunity(request).isSuccessful } catch (_: Exception) { false }
    }

    suspend fun uploadImage(bytes: ByteArray, fileName: String = "image.jpg"): Result<UploadImageResponse> {
        return try {
            val mediaType = "image/*".toMediaTypeOrNull()
            val requestBody = bytes.toRequestBody(mediaType)
            val part = MultipartBody.Part.createFormData("image", fileName, requestBody)
            val resp = api.uploadCommunityImage(part)
            if (resp.isSuccessful) Result.success(resp.body()!!) else Result.failure(Exception(parseError(resp.code())))
        } catch (e: Exception) { Result.failure(e) }
    }

    private fun parseError(code: Int): String = when (code) {
        409 -> "请先选择你的大学"
        404 -> "帖子不存在"
        403 -> "无权操作"
        else -> "请求失败 ($code)"
    }
}
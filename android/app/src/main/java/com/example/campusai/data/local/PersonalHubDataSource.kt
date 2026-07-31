package com.example.campusai.data.local

import com.example.campusai.data.model.PersonalHubSnapshot
import kotlinx.coroutines.flow.Flow

/**
 * 账号个人内容的数据边界。
 *
 * 当前由 DataStore 实现；未来接入云端数据库时只需替换此接口实现，
 * AppRepository 与 Compose UI 无需感知存储位置。
 */
interface PersonalHubDataSource {
    fun observePersonalHub(accountKey: String): Flow<PersonalHubSnapshot?>
    suspend fun savePersonalHub(accountKey: String, snapshot: PersonalHubSnapshot)
}

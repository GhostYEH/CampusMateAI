package com.example.campusai.data.model

/**
 * “我的”页下的账号数据。
 *
 * 这些模型不依赖 DataStore 或网络协议，后续接入云端数据库时可以直接由远端
 * data source 映射到同一组 UI 模型。
 */
data class CampusFile(
    val id: String,
    val name: String,
    val category: String,
    val sizeLabel: String,
    val updatedAt: String,
    val source: String,
    val isFavorite: Boolean = false,
)

data class CampusActivity(
    val id: String,
    val title: String,
    val organizer: String,
    val date: String,
    val location: String,
    val status: String,
    val isFavorite: Boolean = false,
)

data class FavoriteItem(
    val id: String,
    val title: String,
    val type: String,
    val subtitle: String,
    val savedAt: String,
    val sourceRoute: String,
)

data class PersonalHubSnapshot(
    val files: List<CampusFile> = emptyList(),
    val activities: List<CampusActivity> = emptyList(),
    val favorites: List<FavoriteItem> = emptyList(),
)

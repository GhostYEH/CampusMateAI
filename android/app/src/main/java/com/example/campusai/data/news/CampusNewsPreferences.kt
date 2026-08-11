package com.example.campusai.data.news

import kotlinx.coroutines.flow.Flow

interface CampusNewsPreferences {
    val campusNewsReadIds: Flow<Set<String>>
    val campusNewsFavoriteIds: Flow<Set<String>>

    suspend fun setCampusNewsReadIds(ids: Set<String>)
    suspend fun setCampusNewsFavoriteIds(ids: Set<String>)
}

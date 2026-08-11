package com.example.campusai.ui.screens.lostfound

import com.example.campusai.data.model.LostFoundKind

data class LostFoundBrowseState(
    val kind: LostFoundKind = LostFoundKind.LOST,
    val keyword: String = "",
    val category: String = "全部",
    val location: String = "全部地点",
    val newestFirst: Boolean = true,
) {
    fun repositoryLocation(): String = if (location == "全部地点") "全部" else location
}

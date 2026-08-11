package com.example.campusai.ui.screens.lostfound

import com.example.campusai.data.model.LostFoundKind

object LostFoundBrowseOptions {
    const val AllLocation = "全部地点"

    val locations = listOf(
        AllLocation,
        "图书馆三楼",
        "教学楼 2-305",
        "第二食堂",
        "东操场看台",
    )
}

data class LostFoundBrowseState(
    val kind: LostFoundKind = LostFoundKind.LOST,
    val keyword: String = "",
    val category: String = "全部",
    val location: String = LostFoundBrowseOptions.AllLocation,
    val newestFirst: Boolean = true,
) {
    fun repositoryLocation(): String = if (location == LostFoundBrowseOptions.AllLocation) "全部" else location
}

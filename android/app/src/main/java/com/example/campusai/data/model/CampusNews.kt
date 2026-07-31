package com.example.campusai.data.model

/**
 * 校园动态条目数据模型。
 * 用于「校园动态」卡片及详情展示。
 */
data class CampusNews(
    val id: String,
    val title: String,
    val summary: String,
    val content: String,
    val source: String,
    val time: String,
    val category: String = "综合",
    val imageRes: String? = null,
    val tags: List<String> = emptyList(),
    val relatedTasks: List<String> = emptyList(),
)

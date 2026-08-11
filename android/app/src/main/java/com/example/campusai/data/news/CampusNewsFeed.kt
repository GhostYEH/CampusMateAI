package com.example.campusai.data.news

import com.example.campusai.data.model.CampusNews

enum class NewsSort { LATEST, IMPORTANT }

data class NewsFeedQuery(
    val keyword: String = "",
    val category: String = "全部",
    val unreadOnly: Boolean = false,
    val sort: NewsSort = NewsSort.LATEST,
)

data class NewsFeedItem(
    val news: CampusNews,
    val isRead: Boolean,
    val isFavorite: Boolean,
)

fun buildCampusNewsFeed(
    items: List<CampusNews>,
    query: NewsFeedQuery,
    readIds: Set<String>,
    favoriteIds: Set<String>,
): List<NewsFeedItem> {
    val keyword = query.keyword.trim()
    val filteredItems = items.filter { news ->
        (query.category == "全部" || news.category == query.category) &&
            (!query.unreadOnly || news.id !in readIds) &&
            (keyword.isEmpty() || news.matchesKeyword(keyword))
    }
    val sortedItems = when (query.sort) {
        NewsSort.LATEST -> filteredItems
        NewsSort.IMPORTANT -> filteredItems.filter { it.relatedTasks.isNotEmpty() } +
            filteredItems.filter { it.relatedTasks.isEmpty() }
    }

    return sortedItems.map { news ->
        NewsFeedItem(
            news = news,
            isRead = news.id in readIds,
            isFavorite = news.id in favoriteIds,
        )
    }
}

private fun CampusNews.matchesKeyword(keyword: String): Boolean =
    listOf(title, summary, source, category)
        .plus(tags)
        .any { value -> value.contains(keyword, ignoreCase = true) }

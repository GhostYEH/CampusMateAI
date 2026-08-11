package com.example.campusai.data.news

import com.example.campusai.data.model.CampusNews
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CampusNewsFeedTest {

    @Test
    fun queryMatchesTitleSourceAndTagsIgnoringCase() {
        val result = buildCampusNewsFeed(
            items = listOf(
                news(id = "title", title = "LIBRARY closes early"),
                news(id = "source", source = "Library Services"),
                news(id = "tag", tags = listOf("LiBrArY")),
                news(id = "other"),
            ),
            query = NewsFeedQuery(keyword = "library"),
            readIds = emptySet(),
            favoriteIds = emptySet(),
        )

        assertEquals(listOf("title", "source", "tag"), result.map { it.news.id })
    }

    @Test
    fun queryCombinesCategoryAndUnreadFilters() {
        val result = buildCampusNewsFeed(
            items = listOf(
                news(id = "activity-read", category = "活动"),
                news(id = "activity-unread", category = "活动"),
                news(id = "notice-unread", category = "通知"),
            ),
            query = NewsFeedQuery(category = "活动", unreadOnly = true),
            readIds = setOf("activity-read"),
            favoriteIds = emptySet(),
        )

        assertEquals(listOf("activity-unread"), result.map { it.news.id })
    }

    @Test
    fun importantSortPlacesActionableNewsFirstAndPreservesTieOrder() {
        val result = buildCampusNewsFeed(
            items = listOf(
                news(id = "regular-first"),
                news(id = "actionable-first", relatedTasks = listOf("register")),
                news(id = "regular-second"),
                news(id = "actionable-second", relatedTasks = listOf("submit")),
            ),
            query = NewsFeedQuery(sort = NewsSort.IMPORTANT),
            readIds = emptySet(),
            favoriteIds = emptySet(),
        )

        assertEquals(
            listOf("actionable-first", "actionable-second", "regular-first", "regular-second"),
            result.map { it.news.id },
        )
    }

    @Test
    fun feedDecoratesItemsWithSuppliedReadAndFavoriteIds() {
        val result = buildCampusNewsFeed(
            items = listOf(news(id = "read-favorite"), news(id = "unread")),
            query = NewsFeedQuery(),
            readIds = setOf("read-favorite"),
            favoriteIds = setOf("read-favorite"),
        )

        assertTrue(result[0].isRead)
        assertTrue(result[0].isFavorite)
        assertFalse(result[1].isRead)
        assertFalse(result[1].isFavorite)
    }

    @Test
    fun blankKeywordMatchesEveryItemInSourceOrder() {
        val result = buildCampusNewsFeed(
            items = listOf(news(id = "first"), news(id = "second")),
            query = NewsFeedQuery(keyword = "   "),
            readIds = emptySet(),
            favoriteIds = emptySet(),
        )

        assertEquals(listOf("first", "second"), result.map { it.news.id })
    }

    private fun news(
        id: String,
        title: String = "Campus update",
        source: String = "Campus Office",
        category: String = "综合",
        tags: List<String> = emptyList(),
        relatedTasks: List<String> = emptyList(),
    ) = CampusNews(
        id = id,
        title = title,
        summary = "Summary",
        content = "Content",
        source = source,
        time = "2026-08-11",
        category = category,
        tags = tags,
        relatedTasks = relatedTasks,
    )
}

# 鏍″洯璧勮涓績 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax.

**Goal:** Add a full-screen Android campus-news hub with search, category/unread filters, importance sorting, read/favorite persistence, refresh, and detail navigation.

**Architecture:** Keep filtering and sorting in pure Kotlin for unit testing. AppDataStore stores read/favorite IDs, AppRepository exposes flows and mutations, and the Compose screen owns only transient query state.

**Tech Stack:** Kotlin, Jetpack Compose Material 3, Navigation Compose, DataStore Preferences, Kotlin Flow, JUnit 4.

## Global Constraints

- Reuse CampusNews, existing color tokens, CampusPageHeader, FilterChipRow, and the campus-news-detail route.
- Do not add a backend API, dependency, or alternate news source.
- Refresh must not clear local read or favorite IDs.
- Do not stage unrelated existing changes.

---

## File Structure

- Create android/app/src/main/java/com/example/campusai/data/news/CampusNewsFeed.kt: pure filtering, sorting and view data.
- Create android/app/src/test/java/com/example/campusai/data/news/CampusNewsFeedTest.kt: feed behavior tests.
- Modify android/app/src/main/java/com/example/campusai/data/local/AppDataStore.kt: read/favorite persistence.
- Modify android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt: preference flows and mutations.
- Create android/app/src/main/java/com/example/campusai/ui/screens/notifications/CampusNewsScreen.kt: page layout and controls.
- Modify AppNavHost.kt, DashboardScreen.kt, and SecondaryDestinationSpecTest.kt: navigation integration.

### Task 1: Test and implement pure feed behavior

**Files:**
- Create: android/app/src/main/java/com/example/campusai/data/news/CampusNewsFeed.kt
- Create: android/app/src/test/java/com/example/campusai/data/news/CampusNewsFeedTest.kt

**Interfaces:**
- Consumes: CampusNews.
- Produces: NewsSort, NewsFeedQuery, NewsFeedItem, and buildCampusNewsFeed(items, query, readIds, favoriteIds).

- [ ] **Step 1: Write failing tests**

~~~kotlin
@Test fun queryMatchesTitleSourceAndTagsIgnoringCase() {
    val result = buildCampusNewsFeed(sampleNews, NewsFeedQuery(keyword = "library"), emptySet(), emptySet())
    assertEquals(listOf("library"), result.map { it.news.id })
}

@Test fun queryCombinesCategoryAndUnreadFilters() {
    val result = buildCampusNewsFeed(sampleNews, NewsFeedQuery(category = "娲诲姩", unreadOnly = true), setOf("activity-read"), emptySet())
    assertEquals(listOf("activity-unread"), result.map { it.news.id })
}

@Test fun importantSortPlacesActionableNewsFirst() {
    val result = buildCampusNewsFeed(sampleNews, NewsFeedQuery(sort = NewsSort.IMPORTANT), emptySet(), emptySet())
    assertEquals("actionable", result.first().news.id)
}
~~~

- [ ] **Step 2: Verify red**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.data.news.CampusNewsFeedTest

Expected: compilation fails because the feed module does not yet exist.

- [ ] **Step 3: Implement the minimum feed module**

~~~kotlin
enum class NewsSort { LATEST, IMPORTANT }

data class NewsFeedQuery(
    val keyword: String = "",
    val category: String = "鍏ㄩ儴",
    val unreadOnly: Boolean = false,
    val sort: NewsSort = NewsSort.LATEST,
)

data class NewsFeedItem(val news: CampusNews, val isRead: Boolean, val isFavorite: Boolean)

fun buildCampusNewsFeed(
    items: List<CampusNews>,
    query: NewsFeedQuery,
    readIds: Set<String>,
    favoriteIds: Set<String>,
): List<NewsFeedItem>
~~~

The function filters category, unread IDs, then a trimmed case-insensitive keyword against title, summary, source, category and tags. Latest preserves repository order; important puts items with relatedTasks first and preserves ties.

- [ ] **Step 4: Verify green**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.data.news.CampusNewsFeedTest

Expected: every feed test passes.

- [ ] **Step 5: Commit**

~~~powershell
git add android/app/src/main/java/com/example/campusai/data/news/CampusNewsFeed.kt android/app/src/test/java/com/example/campusai/data/news/CampusNewsFeedTest.kt
git commit -m "feat: add campus news feed filtering"
~~~

### Task 2: Persist read and favorite IDs

**Files:**
- Modify: android/app/src/main/java/com/example/campusai/data/local/AppDataStore.kt
- Modify: android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt

**Interfaces:**
- Produces: newsReadIds: StateFlow<Set<String>>, newsFavoriteIds: StateFlow<Set<String>>, markCampusNewsRead(newsId), and toggleCampusNewsFavorite(newsId).

- [ ] **Step 1: Write a persistence contract test**

Keep read/favorite decoration coverage in Task 1. Add a focused test for the repository-facing preference mutation contract: adding an ID is idempotent, and favorite toggling adds then removes exactly that ID. Use a small fake storage seam if the existing repository constructor cannot be instantiated in a unit test.

- [ ] **Step 2: Verify red**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.data.news.CampusNewsPreferencesTest

Expected: compilation fails because the preference storage interface or mutation implementation does not yet exist.

- [ ] **Step 3: Implement persistence**

In AppDataStore, use stringSetPreferencesKey for campus_news_read_ids and campus_news_favorite_ids; map absent values to emptySet. Add writers:

~~~kotlin
suspend fun setCampusNewsReadIds(ids: Set<String>) = context.dataStore.edit {
    it[KEY_CAMPUS_NEWS_READ_IDS] = ids
}
suspend fun setCampusNewsFavoriteIds(ids: Set<String>) = context.dataStore.edit {
    it[KEY_CAMPUS_NEWS_FAVORITE_IDS] = ids
}
~~~

In AppRepository, collect both flows into private MutableStateFlow(emptySet()) fields. Implement:

~~~kotlin
suspend fun markCampusNewsRead(newsId: String) {
    if (newsId !in _newsReadIds.value) dataStore.setCampusNewsReadIds(_newsReadIds.value + newsId)
}

suspend fun toggleCampusNewsFavorite(newsId: String) {
    val ids = _newsFavoriteIds.value
    dataStore.setCampusNewsFavoriteIds(if (newsId in ids) ids - newsId else ids + newsId)
}
~~~

- [ ] **Step 4: Verify green and commit**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.data.news.CampusNewsFeedTest

Expected: all feed tests pass.

~~~powershell
git add android/app/src/main/java/com/example/campusai/data/local/AppDataStore.kt android/app/src/main/java/com/example/campusai/data/repository/AppRepository.kt android/app/src/test/java/com/example/campusai/data/news/CampusNewsPreferencesTest.kt
git commit -m "feat: persist campus news preferences"
~~~

### Task 3: Build and route the hub screen

**Files:**
- Create: android/app/src/main/java/com/example/campusai/ui/screens/notifications/CampusNewsScreen.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt
- Modify: android/app/src/main/java/com/example/campusai/ui/screens/dashboard/DashboardScreen.kt
- Modify: android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt

**Interfaces:**
- CampusNewsScreen(repository: AppRepository, onBack: () -> Unit, onOpenNews: (String) -> Unit)
- Route: campus-news.

- [ ] **Step 1: Write the failing navigation specification**

~~~kotlin
@Test fun campusNewsRouteHasSecondaryTitle() {
    assertEquals("鏍″洯鍔ㄦ€?, secondaryDestinationSpec("campus-news")?.title)
}
~~~

- [ ] **Step 2: Verify red**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest

Expected: assertion fails because campus-news has not been registered.

- [ ] **Step 3: Implement the screen**

Collect news, read IDs and favorite IDs; keep keyword, selected category, unread-only and sort in rememberSaveable; derive categories from nonblank existing categories plus 鍏ㄩ儴; derive feed results with buildCampusNewsFeed.

Use a LazyColumn with status-bar padding, CampusPageHeader (back plus refresh), OutlinedTextField, FilterChipRow, latest/important control, all/unread control, result count, a featured first card, regular cards, and no-data/no-match/error states. Use existing tokens and rounded cards. Opening news marks it read before navigation; the favorite icon toggles without opening detail.

Add the route:

~~~kotlin
composable("campus-news") {
    CampusNewsScreen(
        repository = repository,
        onBack = { navController.popBackStack() },
        onOpenNews = { id -> go("campus-news-detail/$id") },
    )
}
~~~

Change only the dashboard action to onNavigate("campus-news"); preserve home-card detail navigation.

- [ ] **Step 4: Verify green and commit**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest --tests com.example.campusai.data.news.CampusNewsFeedTest --tests com.example.campusai.ui.navigation.SecondaryDestinationSpecTest; .\gradlew.bat :app:compileDebugKotlin

Expected: targeted tests pass and Kotlin compiles without error.

~~~powershell
git add android/app/src/main/java/com/example/campusai/ui/screens/notifications/CampusNewsScreen.kt android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt android/app/src/main/java/com/example/campusai/ui/screens/dashboard/DashboardScreen.kt android/app/src/test/java/com/example/campusai/ui/navigation/SecondaryDestinationSpecTest.kt
git commit -m "feat: add campus news hub"
~~~

### Task 4: Verify the completed feature

- [ ] **Step 1: Run all Android unit tests**

Run: cd android; .\gradlew.bat :app:testDebugUnitTest

Expected: all tests pass.

- [ ] **Step 2: Build the debug APK**

Run: cd android; .\gradlew.bat :app:assembleDebug

Expected: android/app/build/outputs/apk/debug/app-debug.apk is produced.

- [ ] **Step 3: Confirm scope**

Run: git diff HEAD~3..HEAD --check; git status --short

Expected: no feature whitespace errors and no unrelated user-owned file is staged.

## Plan Self-Review

- The plan covers navigation, full list controls, local persistence, empty/failure states, unit tests, compilation, and APK build.
- It relies only on types defined above and has no deferred implementation steps.
- CampusNews.time is display text, so latest correctly preserves repository/API order instead of inventing a fragile parser.

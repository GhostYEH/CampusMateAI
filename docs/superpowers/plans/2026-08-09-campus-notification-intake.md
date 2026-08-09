# Campus Notification Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-authorized, local-only Android system-notification inbox for WeChat and Chaoxing without invoking AI extraction or creating tasks.

**Architecture:** `CampusNotificationListenerService` converts a `StatusBarNotification` to a narrow domain model, resolves its source, filters it using persisted source switches, fingerprints it, and requests an insert from a Room-backed repository. The Compose notifications screen observes repository `Flow`s, manages source switches, and opens Android's notification-listener settings; the existing manual paste workflow remains independent.

**Tech Stack:** Kotlin, Android NotificationListenerService, Room 2.6.1 with kapt, DataStore Preferences, Kotlin Flow, Jetpack Compose Material 3, JUnit 4.

## Global Constraints

- Keep Kotlin 2.0.21, AGP 8.13.0, Gradle Wrapper, Android SDK, and system configuration unchanged.
- Store captured notification content only in the local Room database; never log or upload it.
- Do not add AccessibilityService, WorkManager/AlarmManager reminder behavior, AI extraction calls, or automatic task creation.
- Default source settings are WeChat and Chaoxing on; QQ and Other off.
- Exclude the Room database file from cloud backup and device transfer.

---

### Task 1: Test the pure notification domain pipeline

**Files:**
- Create: `android/app/src/test/java/com/example/campusai/data/notification/NotificationSourceResolverTest.kt`
- Create: `android/app/src/test/java/com/example/campusai/data/notification/NotificationFingerprintTest.kt`
- Create: `android/app/src/test/java/com/example/campusai/data/notification/NotificationFilterTest.kt`
- Create: `android/app/src/test/java/com/example/campusai/data/notification/NotificationTextSanitizerTest.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationSource.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationSourceResolver.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationFingerprint.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationFilter.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationTextSanitizer.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/CapturedNotification.kt`

**Interfaces:**
- Produces `NotificationSourceResolver.resolve(packageName: String): NotificationSource`.
- Produces `NotificationFingerprint.create(notification: CapturedNotification): String`.
- Produces `NotificationFilter.shouldStore(notification: CapturedNotification, settings: NotificationSourceSettings, campusMatePackage: String): Boolean`.

- [ ] Write tests for known package resolution, distinct content/conversations/packages producing distinct hashes, duplicate input producing the same hash, source switches, self/empty/group-summary filtering, and text normalization preference.
- [ ] Run `gradlew.bat :app:testDebugUnitTest --tests "com.example.campusai.data.notification.*"`; confirm the tests fail because the types do not exist.
- [ ] Implement the smallest pure-Kotlin models and pipeline needed to pass the tests.
- [ ] Re-run the focused test command; confirm it passes.

### Task 2: Add local persistence and source configuration

**Files:**
- Modify: `android/gradle/libs.versions.toml`
- Modify: `android/app/build.gradle.kts`
- Modify: `android/app/src/main/java/com/example/campusai/data/local/AppDataStore.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/local/notification/RawNotificationEntity.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/local/notification/RawNotificationDao.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/local/notification/CampusMateDatabase.kt`

**Interfaces:**
- `RawNotificationDao.observeRecent(limit: Int): Flow<List<RawNotificationEntity>>`.
- `RawNotificationDao.insertIgnore(entity: RawNotificationEntity): Long` with a unique `fingerprint` index.
- `AppDataStore.notificationSourceSettings: Flow<NotificationSourceSettings>` and `setNotificationSourceEnabled(source, enabled)`.

- [ ] Add Room runtime, KTX, compiler, and the Kotlin kapt plugin without changing build-tool versions.
- [ ] Implement a v1 Room database named `campusmate_notifications.db`, DAO CRUD operations, and DataStore source switches.
- [ ] Exclude `campusmate_notifications.db` from Auto Backup and Android 12+ cloud/device-transfer rules.
- [ ] Compile debug Kotlin to validate generated Room code.

### Task 3: Add repository and system listener

**Files:**
- Create: `android/app/src/main/java/com/example/campusai/data/repository/NotificationInboxRepository.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/NotificationNormalizer.kt`
- Create: `android/app/src/main/java/com/example/campusai/data/notification/CampusNotificationListenerService.kt`
- Modify: `android/app/src/main/java/com/example/campusai/CampusAIApplication.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Delete: `android/app/src/main/java/com/example/campusai/services/WeChatNoticeListenerService.kt`

**Interfaces:**
- `NotificationInboxRepository.observeRecentNotifications(limit: Int): Flow<List<InboxNotification>>`.
- `NotificationInboxRepository.capture(notification: CapturedNotification): Boolean`.
- `NotificationInboxRepository.isNotificationAccessGranted(): Boolean`.
- `NotificationInboxRepository.createNotificationAccessSettingsIntent(): Intent`.

- [ ] Implement `NotificationNormalizer` as the only Android-framework adapter and preserve no raw notification values in logs.
- [ ] Implement the repository with application context, a Room DAO, and DataStore switches.
- [ ] Register the replacement `NotificationListenerService`, use a cancellable `SupervisorJob` scope, and insert on an IO dispatcher.
- [ ] Remove the prior listener that queued data for server upload/AI processing.

### Task 4: Integrate the existing Compose notifications page

**Files:**
- Modify: `android/app/src/main/java/com/example/campusai/MainActivity.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/navigation/AppNavHost.kt`
- Modify: `android/app/src/main/java/com/example/campusai/ui/screens/notifications/NotificationsScreen.kt`

**Interfaces:**
- `NotificationsScreen(repository: AppRepository, inboxRepository: NotificationInboxRepository)`.

- [ ] Wire the application-owned inbox repository through the existing navigation stack.
- [ ] Add an `自动收集校园通知` Material 3 section with permission status, source switches, empty state, recent local records, per-record deletion, and a confirmed clear action.
- [ ] Refresh the permission state on lifecycle resume and keep the manual paste/extract section intact.
- [ ] Build the debug APK to validate Compose integration.

### Task 5: Documentation, regression verification, and review

**Files:**
- Modify: `README.md`

- [ ] Add a minimal README statement covering consent-based system notifications, WeChat/Chaoxing priority, local-only storage, no complete chat history, and Phase 2B remaining work.
- [ ] Run serial `:app:compileDebugKotlin`, `:app:testDebugUnitTest`, `:app:assembleDebug`, and `:app:lintDebug`.
- [ ] Inspect `git diff`, verify no raw notification samples, build outputs, SDK/config changes, or web-dist user changes are included, and report manual device validation steps.

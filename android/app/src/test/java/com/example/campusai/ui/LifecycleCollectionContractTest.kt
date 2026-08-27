package com.example.campusai.ui

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LifecycleCollectionContractTest {
    @Test
    fun composeFlowsUseLifecycleAwareCollectionOutsideEduConnectionWork() {
        val sourceRoot = sourceRoot()
        val offenders = sourceRoot.walkTopDown()
            .filter { it.isFile && it.extension == "kt" }
            .filterNot { it.name == "EduSystemScreen.kt" }
            .filter { it.readText().contains(".collectAsState(") }
            .map { it.relativeTo(sourceRoot).path }
            .toList()

        assertTrue("Non-lifecycle-aware Flow collectors: $offenders", offenders.isEmpty())
    }

    @Test
    fun periodicWorkIsOwnedByApplicationInsteadOfActivity() {
        val root = sourceRoot()
        val activity = File(root, "com/example/campusai/MainActivity.kt").readText()
        val application = File(root, "com/example/campusai/CampusAIApplication.kt").readText()

        assertFalse(activity.contains("enqueueUniquePeriodicWork"))
        assertTrue(application.contains("ChaoxingSyncScheduler(this@CampusAIApplication).scheduleSyncWork()"))
        assertTrue(application.contains("Dispatchers.Default"))
    }

    private fun sourceRoot(): File {
        val candidates = listOf(File("src/main/java"), File("app/src/main/java"))
        return requireNotNull(candidates.firstOrNull(File::isDirectory)) {
            "Unable to locate Android production sources"
        }
    }
}

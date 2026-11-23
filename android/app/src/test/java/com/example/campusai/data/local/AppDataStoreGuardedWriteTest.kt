package com.example.campusai.data.local

import android.app.Application
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class AppDataStoreGuardedWriteTest {

    @Test
    fun `guarded write drops a stale value at the datastore boundary`() = runTest {
        val store = AppDataStore(ApplicationProvider.getApplicationContext<Application>())
        val key = "classroom_write_guard_test"

        store.saveRawIf(key, "new", shouldWrite = { true })
        store.saveRawIf(key, "old", shouldWrite = { false })

        assertEquals("new", store.readRaw(key))
    }
}

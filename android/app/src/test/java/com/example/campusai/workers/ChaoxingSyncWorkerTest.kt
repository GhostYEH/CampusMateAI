package com.example.campusai.workers

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker
import androidx.work.testing.TestListenableWorkerBuilder
import com.example.campusai.CampusAIApplication
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowNotificationManager

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33], application = CampusAIApplication::class)
class ChaoxingSyncWorkerTest {

    private lateinit var context: Context
    private lateinit var stateStore: ChaoxingSyncStateStore
    private lateinit var appRepository: AppRepository

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        stateStore = ChaoxingSyncStateStore(context)
        appRepository = (context as CampusAIApplication).repository
    }

    @Test
    fun testWorker_notConnected_returnsSuccessAndDoesNothing() = runBlocking {
        stateStore.setConnected(false)
        val worker = TestListenableWorkerBuilder<ChaoxingSyncWorker>(context).build()
        val result = worker.doWork()
        
        assertTrue(result is ListenableWorker.Result.Success)
    }
}
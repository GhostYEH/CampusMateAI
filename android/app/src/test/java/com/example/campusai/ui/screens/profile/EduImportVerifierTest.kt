package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemsResponse
import com.example.campusai.data.remote.EduSyncResult
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EduImportVerifierTest {
    @Test
    fun persistedScheduleWithoutItemsIsNotAnImportedSchedule() {
        assertFalse(isScheduleImported(
            EduSyncResult(sync_type = "schedule", status = "success", items_count = 0, persisted = true),
            EduScheduleItemsResponse(items_count = 0),
        ))
    }

    @Test
    fun persistedScheduleThatCanBeReadBackIsImported() {
        assertTrue(isScheduleImported(
            EduSyncResult(sync_type = "schedule", status = "success", items_count = 3, persisted = true),
            EduScheduleItemsResponse(items_count = 3),
        ))
    }
}

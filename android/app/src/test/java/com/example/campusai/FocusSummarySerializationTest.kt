package com.example.campusai

import com.example.campusai.BuildConfig
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.data.model.FocusBehaviorSummary
import com.example.campusai.data.remote.StudyBehaviorSummaryDto
import com.example.campusai.data.remote.StudySessionFinishRequest
import com.example.campusai.ui.screens.focus.toCounselorPrompt
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class FocusSummarySerializationTest {
    @Test fun summaryRoundTripsAndDebugDefaultsToReal() {
        val behaviorSummary = FocusBehaviorSummary(
            observedSeconds = 600,
            studySeconds = 510,
            pausedSeconds = 60,
            longestContinuousStudySeconds = 330,
            meaningfulSwitchCount = 2,
            phoneInteractionCount = 1,
            possibleDistractionCount = 1,
            absentCount = 0,
            reminderCount = 1,
            modelVersion = "READY_BEHAVIOR_HYBRID_V4",
        )
        val summary = FocusSessionSummary(
            25, 1, 12, 1, mapOf("NEUTRAL" to 8), "litert-v1", behaviorSummary,
        )
        val adapter = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build().adapter(FocusSessionSummary::class.java)
        assertEquals(summary, adapter.fromJson(adapter.toJson(summary)))
        org.junit.Assert.assertTrue(adapter.toJson(summary).contains("READY_BEHAVIOR_HYBRID_V4"))
        val prompt = summary.toCounselorPrompt()
        org.junit.Assert.assertTrue(prompt.contains("由用户主动发送"))
        org.junit.Assert.assertTrue(prompt.contains("不包含、也未发送任何照片、视频或逐帧结果"))
        assertFalse(BuildConfig.DEFAULT_USE_MOCK)
    }

    @Test fun finishRequestUsesPrivacySafeSnakeCaseBehaviorSummary() {
        val request = StudySessionFinishRequest(
            self_report = "完成专注",
            behavior_summary = StudyBehaviorSummaryDto(
                observed_seconds = 600,
                study_seconds = 510,
                paused_seconds = 60,
                longest_continuous_study_seconds = 330,
                meaningful_switch_count = 2,
                phone_interaction_count = 1,
                possible_distraction_count = 1,
                absent_count = 0,
                reminder_count = 1,
                model_version = "READY_BEHAVIOR_HYBRID_V4",
            ),
        )
        val adapter = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
            .adapter(StudySessionFinishRequest::class.java)
        val json = adapter.toJson(request)

        org.junit.Assert.assertTrue(json.contains("\"behavior_summary\""))
        org.junit.Assert.assertTrue(json.contains("\"observed_seconds\":600"))
        assertFalse(json.contains("frame"))
        assertFalse(json.contains("image"))
    }
}

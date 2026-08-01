package com.example.campusai

import com.example.campusai.BuildConfig
import com.example.campusai.data.model.FocusSessionSummary
import com.example.campusai.ui.screens.focus.toCounselorPrompt
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class FocusSummarySerializationTest {
    @Test fun summaryRoundTripsAndDebugDefaultsToReal() {
        val summary = FocusSessionSummary(25, 1, 12, 1, mapOf("NEUTRAL" to 8), "litert-v1")
        val adapter = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build().adapter(FocusSessionSummary::class.java)
        assertEquals(summary, adapter.fromJson(adapter.toJson(summary)))
        val prompt = summary.toCounselorPrompt()
        org.junit.Assert.assertTrue(prompt.contains("由用户主动发送"))
        org.junit.Assert.assertTrue(prompt.contains("不包含、也未发送任何照片、视频或逐帧结果"))
        assertFalse(BuildConfig.DEFAULT_USE_MOCK)
    }
}

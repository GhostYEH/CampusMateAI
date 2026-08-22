package com.example.campusai.expression_recognition_android_test

import com.example.campusai.ExpressionPerformanceStatsTest
import com.example.campusai.ExpressionSignalProcessorTest
import com.example.campusai.FaceQualityGateTest
import com.example.campusai.ImageProxyBitmapConverterTest
import org.junit.runner.RunWith
import org.junit.runners.Suite

/**
 * Named regression suite for the Android expression-recognition contract.
 * The cases run as JVM tests so they remain available without a connected device.
 */
@RunWith(Suite::class)
@Suite.SuiteClasses(
    ExpressionPerformanceStatsTest::class,
    ExpressionSignalProcessorTest::class,
    ImageProxyBitmapConverterTest::class,
    FaceQualityGateTest::class,
)
class ExpressionRecognitionAndroidTest

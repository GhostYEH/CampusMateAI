package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BehaviorSignalProcessorTest {

    @Test
    fun testPhoneDistraction() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(phoneUseThresholdMs = 3000L)
        )
        
        // 1s: Start using phone
        val events1 = processor.process(
            BehaviorPrediction(mapOf(StudyBehavior.PHONE_USE to 0.8f), 1000L, "READY")
        )
        assertTrue(events1.isEmpty())
        
        // 3s: Still using phone, but under threshold
        val events2 = processor.process(
            BehaviorPrediction(mapOf(StudyBehavior.PHONE_USE to 0.8f), 3000L, "READY")
        )
        assertTrue(events2.isEmpty())
        
        // 5s: Using phone past threshold -> Event generated
        val events3 = processor.process(
            BehaviorPrediction(mapOf(StudyBehavior.PHONE_USE to 0.8f), 5000L, "READY")
        )
        assertEquals(1, events3.size)
        assertEquals(StableBehaviorEvent.PHONE_DISTRACTION, events3[0])
    }
    
    @Test
    fun testShortPhoneUseIgnored() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(phoneUseThresholdMs = 3000L)
        )
        
        // 1s: Start using phone
        processor.process(BehaviorPrediction(mapOf(StudyBehavior.PHONE_USE to 0.8f), 1000L, "READY"))
        
        // 3s: Stop using phone
        val events2 = processor.process(BehaviorPrediction(mapOf(StudyBehavior.WRITING to 0.8f), 3000L, "READY"))
        assertTrue(events2.contains(StableBehaviorEvent.STABLE_LEARNING) || events2.isEmpty())
        
        // 5s: Still writing
        val events3 = processor.process(BehaviorPrediction(mapOf(StudyBehavior.WRITING to 0.8f), 5000L, "READY"))
        assertTrue(events3.none { it == StableBehaviorEvent.PHONE_DISTRACTION })
    }

    @Test
    fun testShortPenSpinningIgnored() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(penFidgetingThresholdMs = 10000L)
        )
        
        // 1s: Start pen spinning
        processor.process(BehaviorPrediction(mapOf(StudyBehavior.PEN_SPINNING to 0.8f), 1000L, "READY"))
        
        // 6s: Still spinning, under threshold
        val events2 = processor.process(BehaviorPrediction(mapOf(StudyBehavior.PEN_SPINNING to 0.8f), 6000L, "READY"))
        assertTrue(events2.isEmpty())
    }

    @Test
    fun testPossibleDistraction() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(penFidgetingThresholdMs = 10000L, lookAwayThresholdMs = 5000L)
        )
        
        // 1s: Start pen spinning and looking away
        processor.process(
            BehaviorPrediction(
                mapOf(StudyBehavior.PEN_SPINNING to 0.8f, StudyBehavior.LOOKING_AWAY to 0.8f, StudyBehavior.WRITING to 0.1f), 
                1000L, "READY"
            )
        )
        
        // 6s: Look away triggers
        val events2 = processor.process(
            BehaviorPrediction(
                mapOf(StudyBehavior.PEN_SPINNING to 0.8f, StudyBehavior.LOOKING_AWAY to 0.8f, StudyBehavior.WRITING to 0.1f), 
                6000L, "READY"
            )
        )
        assertTrue(events2.contains(StableBehaviorEvent.LONG_LOOK_AWAY))
        
        // 11s: Pen spinning triggers with low writing and look away = POSSIBLE_DISTRACTION
        val events3 = processor.process(
            BehaviorPrediction(
                mapOf(StudyBehavior.PEN_SPINNING to 0.8f, StudyBehavior.LOOKING_AWAY to 0.8f, StudyBehavior.WRITING to 0.1f), 
                11000L, "READY"
            )
        )
        assertTrue(events3.contains(StableBehaviorEvent.POSSIBLE_DISTRACTION))
    }

    @Test
    fun testAbsentAndRecovery() {
        val processor = BehaviorSignalProcessor(
            BehaviorSignalConfig(absentThresholdMs = 10000L, learningRecoveryThresholdMs = 5000L)
        )
        
        // 1s: Absent
        processor.process(BehaviorPrediction(mapOf(StudyBehavior.ABSENT to 0.9f), 1000L, "READY"))
        
        // 11s: Still absent
        val events1 = processor.process(BehaviorPrediction(mapOf(StudyBehavior.ABSENT to 0.9f), 11000L, "READY"))
        assertTrue(events1.contains(StableBehaviorEvent.STUDENT_ABSENT))
        
        // 15s: Return and start writing
        processor.process(BehaviorPrediction(mapOf(StudyBehavior.WRITING to 0.8f), 15000L, "READY"))
        
        // 21s: Stable writing for 6s -> FOCUS_RECOVERED
        val events2 = processor.process(BehaviorPrediction(mapOf(StudyBehavior.WRITING to 0.8f), 21000L, "READY"))
        assertTrue(events2.contains(StableBehaviorEvent.FOCUS_RECOVERED))
    }
}

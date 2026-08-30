package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Test

class BehaviorModelSelectionTest {

    @Test
    fun productionUsesV34WhenModelAndPersonRoiAreAvailable() {
        assertEquals(
            BehaviorRuntimeModel.V34,
            BehaviorModelSelection.select(v34Available = true, v32Available = true, hasPersonRoi = true),
        )
    }

    @Test
    fun disabledV34FallsBackToV32ForControlledRollback() {
        assertEquals(
            BehaviorRuntimeModel.V32,
            BehaviorModelSelection.select(
                v34Available = true,
                v32Available = true,
                hasPersonRoi = true,
                enableV34 = false,
            ),
        )
    }

    @Test
    fun missingPersonRoiFallsBackToV32FullFrame() {
        assertEquals(
            BehaviorRuntimeModel.V32,
            BehaviorModelSelection.select(v34Available = true, v32Available = true, hasPersonRoi = false),
        )
    }

    @Test
    fun unavailableV34FallsBackToV32() {
        assertEquals(
            BehaviorRuntimeModel.V32,
            BehaviorModelSelection.select(v34Available = false, v32Available = true, hasPersonRoi = true),
        )
    }

    @Test
    fun reportsUnavailableWhenNeitherModelCanRun() {
        assertEquals(
            BehaviorRuntimeModel.UNAVAILABLE,
            BehaviorModelSelection.select(v34Available = false, v32Available = false, hasPersonRoi = false),
        )
    }
}

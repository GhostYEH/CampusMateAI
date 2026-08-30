package com.example.campusai.data.behavior

enum class BehaviorRuntimeModel {
    V34,
    V32,
    UNAVAILABLE,
}

object BehaviorModelSelection {
    fun select(
        v34Available: Boolean,
        v32Available: Boolean,
        hasPersonRoi: Boolean,
        enableV34: Boolean = true,
    ): BehaviorRuntimeModel = when {
        enableV34 && v34Available && hasPersonRoi -> BehaviorRuntimeModel.V34
        v32Available -> BehaviorRuntimeModel.V32
        else -> BehaviorRuntimeModel.UNAVAILABLE
    }
}

package com.example.campusai.data.behavior

import kotlin.math.exp
import kotlin.math.max

internal object BehaviorModelMath {

    fun softmax2(readLogit: Float, writeLogit: Float): FloatArray {
        val maximum = max(readLogit, writeLogit)

        val readExp = exp((readLogit - maximum).toDouble())
        val writeExp = exp((writeLogit - maximum).toDouble())

        val sum = readExp + writeExp

        return floatArrayOf(
            (readExp / sum).toFloat(),
            (writeExp / sum).toFloat(),
        )
    }
}

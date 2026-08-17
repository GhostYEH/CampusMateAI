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
    fun softmax(logits: FloatArray): FloatArray {
        require(logits.isNotEmpty()) {
            "Logits must not be empty"
        }

        val maximum = logits.maxOrNull()
            ?: error("Logits must not be empty")

        val exponentials = DoubleArray(logits.size)

        var sum = 0.0

        for (index in logits.indices) {
            val value = exp(
                (logits[index] - maximum).toDouble()
            )

            exponentials[index] = value
            sum += value
        }

        return FloatArray(logits.size) { index ->
            (exponentials[index] / sum).toFloat()
        }
    }
}

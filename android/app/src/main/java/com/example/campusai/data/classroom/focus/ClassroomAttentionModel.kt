package com.example.campusai.data.classroom.focus

import android.content.Context
import com.example.campusai.BuildConfig
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import java.io.FileNotFoundException
import kotlin.math.exp
import kotlin.math.min

/**
 * 端侧课堂投入模型。
 *
 * 模型只在学生主动开启且产物通过真实数据发布条件后参与提醒；加载失败、版本不兼容、
 * 特征缺失无法插补或画面不可判断时一律回退到事实观察，不产生专注度/分心结论。
 * 所有计算在本机完成，不读取或上传原始帧。
 */
sealed interface ClassroomAttentionModelLoad {
    object Missing : ClassroomAttentionModelLoad
    data class Unavailable(val reason: String) : ClassroomAttentionModelLoad
    data class Ready(val artifact: ClassroomAttentionArtifact) : ClassroomAttentionModelLoad
}

data class ClassroomAttentionNormalization(val mean: Double, val std: Double)

data class ClassroomAttentionGate(
    val minValidCoverage: Double,
    val minFaceVisibleRatio: Double,
)

data class ClassroomAttentionRelease(
    val eligible: Boolean,
    val reason: String,
    val required: Map<String, Any?>,
)

data class ClassroomAttentionArtifact(
    val schemaVersion: Int,
    val modelVersion: String,
    val featureSet: String,
    val featureOrder: List<String>,
    val featureLabels: Map<String, String>,
    val missingPolicy: String,
    val impute: Map<String, Double>,
    val normalization: Map<String, ClassroomAttentionNormalization>,
    val coefficients: List<Double>,
    val intercept: Double,
    val calibrationA: Double,
    val calibrationB: Double,
    val threshold: Double,
    val gate: ClassroomAttentionGate,
    val release: ClassroomAttentionRelease,
    val trainingDataSource: String?,
)

data class ClassroomAttentionPrediction(
    val probability: Double,
    val logit: Double,
    val threshold: Double,
    val offTask: Boolean,
    val missingFeatureCount: Int,
    val modelVersion: String,
)

object ClassroomAttentionFeatures {
    const val SAMPLE_INTERVAL_MS = 250L

    val KNOWN = setOf(
        "face_visible_ratio",
        "valid_coverage",
        "invalid_ratio",
        "manual_page_turns",
        "quiz_submissions",
        "questions",
        "stage_quiz",
        "stage_lecture",
        "yaw_mean",
        "yaw_std",
        "yaw_range",
        "pitch_mean",
        "pitch_std",
        "pitch_range",
    )

    fun extract(window: ClassroomObservationWindow): Map<String, Double?> {
        val duration = (window.endOffsetMs - window.startOffsetMs).coerceAtLeast(0L)
        val expected = maxOf(1L, duration / SAMPLE_INTERVAL_MS)
        val valid = window.validSampleCount.toDouble()
        val invalid = window.invalidSampleCount.toDouble()
        val samples = valid + invalid
        val yaw = window.yaw
        val pitch = window.pitch
        return mapOf(
            "face_visible_ratio" to window.faceVisibleRatio,
            "valid_coverage" to min(1.0, valid / expected.toDouble()),
            "invalid_ratio" to if (samples > 0) invalid / samples else null,
            "manual_page_turns" to window.manualPageTurns.toDouble(),
            "quiz_submissions" to window.quizSubmissions.toDouble(),
            "questions" to window.questions.toDouble(),
            "stage_quiz" to if (window.dominantStage == "quiz") 1.0 else 0.0,
            "stage_lecture" to if (window.dominantStage == "lecture") 1.0 else 0.0,
            "yaw_mean" to yaw?.mean,
            "yaw_std" to yaw?.standardDeviation,
            "yaw_range" to yaw?.let { it.max - it.min },
            "pitch_mean" to pitch?.mean,
            "pitch_std" to pitch?.standardDeviation,
            "pitch_range" to pitch?.let { it.max - it.min },
        )
    }

    fun gatePassed(artifact: ClassroomAttentionArtifact, window: ClassroomObservationWindow): Boolean =
        window.verdict == ClassroomObservationVerdict.OBSERVABLE &&
            window.faceVisibleRatio >= artifact.gate.minFaceVisibleRatio &&
            (extract(window)["valid_coverage"] ?: 0.0) >= artifact.gate.minValidCoverage
}

object ClassroomAttentionInference {
    /** 面向课堂使用的入口：先通过画面/采样覆盖门槛，再给出离题概率。 */
    fun predict(
        artifact: ClassroomAttentionArtifact,
        window: ClassroomObservationWindow,
    ): ClassroomAttentionPrediction? {
        if (!ClassroomAttentionFeatures.gatePassed(artifact, window)) return null
        return score(artifact, window)
    }

    /**
     * 不做覆盖门槛的纯数值推理，供 Python/Kotlin 一致性测试与 Debug 复盘使用。
     * 正式提醒必须走 [predict]，不能直接把这里的概率当成结论。
     */
    internal fun score(
        artifact: ClassroomAttentionArtifact,
        window: ClassroomObservationWindow,
    ): ClassroomAttentionPrediction? {
        val values = ClassroomAttentionFeatures.extract(window)
        var logit = artifact.intercept
        var missing = 0
        artifact.featureOrder.forEachIndexed { index, name ->
            val raw = values[name]
            val value = if (raw == null) {
                missing += 1
                artifact.impute[name] ?: return null
            } else {
                raw
            }
            val normalization = artifact.normalization[name] ?: return null
            val std = if (normalization.std == 0.0) 1.0 else normalization.std
            logit += artifact.coefficients[index] * ((value - normalization.mean) / std)
        }
        logit = logit.coerceIn(-40.0, 40.0)
        val probability = sigmoid(
            artifact.calibrationA * logit + artifact.calibrationB,
        )
        return ClassroomAttentionPrediction(
            probability = probability,
            logit = logit,
            threshold = artifact.threshold,
            offTask = probability >= artifact.threshold,
            missingFeatureCount = missing,
            modelVersion = artifact.modelVersion,
        )
    }

    fun sigmoid(value: Double): Double = if (value >= 0.0) {
        val z = exp(-min(value, 40.0))
        1.0 / (1.0 + z)
    } else {
        val z = exp(maxOf(value, -40.0))
        z / (1.0 + z)
    }
}

class ClassroomAttentionModelLoader(
    private val openAsset: (String) -> java.io.InputStream,
    private val debugBuild: Boolean = BuildConfig.DEBUG,
) {
    constructor(context: Context) : this({ context.assets.open(it) })

    /**
     * 正式产物固定放在 `classroom_attention/model.json`，Debug 只额外回退到
     * `model-preview.json` 的测试权重。这样将来真实数据训练出的模型放入 main
     * assets 后，Debug 构建也会优先使用正式产物，而不是被预览权重遮蔽。
     */
    fun load(): ClassroomAttentionModelLoad {
        val primary = read(ASSET_PATH)
        if (primary !is ClassroomAttentionModelLoad.Missing || !debugBuild) return primary
        return read(PREVIEW_ASSET_PATH)
    }

    private fun read(assetPath: String): ClassroomAttentionModelLoad {
        val text = try {
            openAsset(assetPath).bufferedReader().use { it.readText() }
        } catch (_: FileNotFoundException) {
            return ClassroomAttentionModelLoad.Missing
        } catch (_: Exception) {
            return ClassroomAttentionModelLoad.Unavailable("模型读取失败")
        }
        return ClassroomAttentionArtifactParser.parse(text)
    }

    companion object {
        const val ASSET_PATH = "classroom_attention/model.json"
        const val PREVIEW_ASSET_PATH = "classroom_attention/model-preview.json"
    }
}

object ClassroomAttentionArtifactParser {
    private val moshi = Moshi.Builder().build()
    private val mapType = Types.newParameterizedType(
        Map::class.java,
        String::class.java,
        Any::class.java,
    )
    private val adapter = moshi.adapter<Map<String, Any?>>(mapType)

    fun parse(text: String): ClassroomAttentionModelLoad {
        val root = try {
            adapter.fromJson(text)
        } catch (_: Exception) {
            null
        } ?: return ClassroomAttentionModelLoad.Unavailable("模型 JSON 无法解析")
        return try {
            ClassroomAttentionModelLoad.Ready(read(root))
        } catch (error: IllegalArgumentException) {
            ClassroomAttentionModelLoad.Unavailable(error.message ?: "模型不兼容")
        } catch (_: Exception) {
            ClassroomAttentionModelLoad.Unavailable("模型字段不兼容")
        }
    }

    private fun read(root: Map<String, Any?>): ClassroomAttentionArtifact {
        val schemaVersion = root.int("schema_version")
            ?: throw IllegalArgumentException("模型缺少 schema_version")
        requireCompat(schemaVersion == 1) { "不支持的模型 schema_version=$schemaVersion" }
        val modelVersion = root.string("model_version")
            ?: throw IllegalArgumentException("模型缺少 model_version")
        val featureSet = root.string("feature_set")
            ?: throw IllegalArgumentException("模型缺少 feature_set")
        val featureOrder = root.list("feature_order").map { it.toString() }
        if (featureOrder.isEmpty()) throw IllegalArgumentException("模型没有特征")
        val unknown = featureOrder.filterNot { it in ClassroomAttentionFeatures.KNOWN }
        requireCompat(unknown.isEmpty()) { "模型含未知特征: ${unknown.joinToString(",")}" }
        val coefficients = root.list("coefficients").map { it.asDouble() }
        requireCompat(coefficients.size == featureOrder.size) { "模型特征数与系数数不一致" }
        val missingPolicy = root.string("missing_policy")
            ?: throw IllegalArgumentException("模型缺少 missing_policy")
        requireCompat(missingPolicy == "median_impute") { "不支持的缺失值策略: $missingPolicy" }
        val imputeMap = root.map("impute")
        val normalizationMap = root.map("normalization")
        val impute = featureOrder.associateWith { name ->
            (imputeMap[name] as? Number)?.toDouble()
                ?: throw IllegalArgumentException("模型缺少 $name 的插补值")
        }
        val normalization = featureOrder.associateWith { name ->
            val stats = normalizationMap[name] as? Map<*, *>
                ?: throw IllegalArgumentException("模型缺少 $name 的归一化参数")
            ClassroomAttentionNormalization(
                mean = (stats["mean"] as? Number)?.toDouble()
                    ?: throw IllegalArgumentException("模型缺少 $name.mean"),
                std = (stats["std"] as? Number)?.toDouble()
                    ?: throw IllegalArgumentException("模型缺少 $name.std"),
            )
        }
        val intercept = root.double("intercept")
            ?: throw IllegalArgumentException("模型缺少 intercept")
        val calibration = root.map("calibration")
        val calibrationType = calibration["type"]?.toString()
        requireCompat(calibrationType == "platt") { "不支持的校准方式: $calibrationType" }
        val calibrationA = (calibration["a"] as? Number)?.toDouble()
            ?: throw IllegalArgumentException("模型缺少校准参数 a")
        val calibrationB = (calibration["b"] as? Number)?.toDouble()
            ?: throw IllegalArgumentException("模型缺少校准参数 b")
        val threshold = root.double("decision_threshold")
            ?: throw IllegalArgumentException("模型缺少 decision_threshold")
        requireCompat(threshold > 0.0 && threshold < 1.0) { "decision_threshold 必须在 0..1 内" }
        val gateMap = root.map("coverage_gate")
        val gate = ClassroomAttentionGate(
            minValidCoverage = (gateMap["min_valid_coverage"] as? Number)?.toDouble()
                ?: throw IllegalArgumentException("模型缺少 min_valid_coverage"),
            minFaceVisibleRatio = (gateMap["min_face_visible_ratio"] as? Number)?.toDouble()
                ?: throw IllegalArgumentException("模型缺少 min_face_visible_ratio"),
        )
        requireCompat(gate.minValidCoverage in 0.0..1.0 && gate.minFaceVisibleRatio in 0.0..1.0) {
            "模型覆盖率门槛非法"
        }
        val releaseMap = root.map("release")
        val releaseEligible = releaseMap["eligible"] as? Boolean
            ?: throw IllegalArgumentException("模型缺少 release.eligible")
        val releaseReason = releaseMap["reason"]?.toString().orEmpty()
        val featureLabels = root.map("feature_labels").mapValues { it.value.toString() }
        val training = root.map("training")
        return ClassroomAttentionArtifact(
            schemaVersion = schemaVersion,
            modelVersion = modelVersion,
            featureSet = featureSet,
            featureOrder = featureOrder,
            featureLabels = featureLabels,
            missingPolicy = missingPolicy,
            impute = impute,
            normalization = normalization,
            coefficients = coefficients,
            intercept = intercept,
            calibrationA = calibrationA,
            calibrationB = calibrationB,
            threshold = threshold,
            gate = gate,
            release = ClassroomAttentionRelease(
                eligible = releaseEligible,
                reason = releaseReason,
                required = (releaseMap["required"] as? Map<String, Any?>).orEmpty(),
            ),
            trainingDataSource = training["data_source"]?.toString(),
        )
    }

    private inline fun requireCompat(condition: Boolean, message: () -> String) {
        if (!condition) throw IllegalArgumentException(message())
    }

    private fun Map<String, Any?>.string(key: String): String? = this[key] as? String

    private fun Map<String, Any?>.double(key: String): Double? =
        (this[key] as? Number)?.toDouble()

    private fun Map<String, Any?>.int(key: String): Int? =
        (this[key] as? Number)?.toInt()

    @Suppress("UNCHECKED_CAST")
    private fun Map<String, Any?>.map(key: String): Map<String, Any?> =
        this[key] as? Map<String, Any?> ?: emptyMap()

    private fun Map<String, Any?>.list(key: String): List<Any?> =
        this[key] as? List<Any?> ?: emptyList()

    private fun Any?.asDouble(): Double =
        (this as? Number)?.toDouble() ?: throw IllegalArgumentException("模型系数不是数值")
}

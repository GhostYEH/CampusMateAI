package com.example.campusai.data.camera

import android.app.Application
import android.os.SystemClock
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.example.campusai.data.expression.ImageProxyBitmapConverter
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

interface FrameAnalyzer {
    fun analyze(frame: CameraFrame)
}

class FocusCameraPipeline(
    private val application: Application
) {
    private var analysisExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var cameraProvider: ProcessCameraProvider? = null
    private var lifecycleOwner: LifecycleOwner? = null
    private var previewView: PreviewView? = null
    private val analyzing = AtomicBoolean(false)
    private var running = false
    private var lastAnalyzedAt = 0L

    private val analyzers = CopyOnWriteArrayList<FrameAnalyzer>()

    fun addAnalyzer(analyzer: FrameAnalyzer) {
        if (!analyzers.contains(analyzer)) {
            analyzers.add(analyzer)
        }
    }

    fun removeAnalyzer(analyzer: FrameAnalyzer) {
        analyzers.remove(analyzer)
    }

    fun start() {
        running = true
        bindUseCasesIfReady()
    }

    fun pause() {
        running = false
        cameraProvider?.unbindAll()
    }

    fun stop() {
        running = false
        cameraProvider?.unbindAll()
    }

    fun dispose() {
        running = false
        cameraProvider?.unbindAll()
        cameraProvider = null
        analysisExecutor.shutdownNow()
        analyzers.clear()
    }

    fun bindCamera(lifecycleOwner: LifecycleOwner, previewView: PreviewView) {
        this.lifecycleOwner = lifecycleOwner
        this.previewView = previewView
        bindUseCasesIfReady()
    }

    fun unbindCamera() {
        cameraProvider?.unbindAll()
        lifecycleOwner = null
        previewView = null
    }

    private fun bindUseCasesIfReady() {
        val owner = lifecycleOwner ?: return
        val view = previewView ?: return
        if (!running) return
        val future = ProcessCameraProvider.getInstance(application)
        future.addListener({
            try {
                val provider = future.get()
                cameraProvider = provider
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(view.surfaceProvider)
                }
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setResolutionSelector(
                        ResolutionSelector.Builder()
                            .setResolutionStrategy(
                                ResolutionStrategy(
                                    Size(640, 480),
                                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER,
                                ),
                            )
                            .build(),
                    )
                    .build()
                    .also { useCase ->
                        useCase.setAnalyzer(analysisExecutor) { image ->
                            processImage(image)
                        }
                    }
                provider.unbindAll()
                provider.bindToLifecycle(
                    owner,
                    CameraSelector.DEFAULT_FRONT_CAMERA,
                    preview,
                    analysis,
                )
            } catch (error: Exception) {
                // Ignore for now, could notify an error listener
            }
        }, ContextCompat.getMainExecutor(application))
    }

    private fun processImage(image: ImageProxy) {
        val now = SystemClock.elapsedRealtime()
        if (!running || now - lastAnalyzedAt < ANALYSIS_INTERVAL_MS ||
            !analyzing.compareAndSet(false, true)
        ) {
            image.close()
            return
        }
        lastAnalyzedAt = now
        val bitmap = try {
            ImageProxyBitmapConverter.toUprightMirroredBitmap(image, mirror = true)
        } catch (error: Exception) {
            image.close()
            analyzing.set(false)
            return
        }
        image.close()

        val frame = CameraFrame(bitmap, System.currentTimeMillis())
        
        try {
            analyzers.forEach { analyzer ->
                try {
                    analyzer.analyze(frame)
                } catch (e: Exception) {
                    // Ignore individual analyzer failures
                }
            }
        } finally {
            frame.release()
            analyzing.set(false)
        }
    }

    companion object {
        private const val ANALYSIS_INTERVAL_MS = 200L
    }
}

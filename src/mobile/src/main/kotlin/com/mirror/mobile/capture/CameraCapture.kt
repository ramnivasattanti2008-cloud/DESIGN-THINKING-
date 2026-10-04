package com.mirror.mobile.capture

import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Matrix
import android.util.Base64
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.mirror.mobile.api.CaptureException
import com.mirror.mobile.api.FrameSource
import com.mirror.mobile.api.FrameUpload
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Takes one real still from the back camera per call, computes blur and brightness on device,
 * and returns a downscaled JPEG. There is no simulated frame here: if the camera is unavailable
 * the call throws [CaptureException].
 */
class CameraCapture(
    private val context: Context,
    private val owner: LifecycleOwner
) : FrameSource {

    private var imageCapture: ImageCapture? = null

    override suspend fun capture(id: String): FrameUpload {
        if (ContextCompat.checkSelfPermission(context, android.Manifest.permission.CAMERA)
            != PackageManager.PERMISSION_GRANTED
        ) throw CaptureException("Camera permission is needed. Allow it in Settings and try again.")

        val capture = imageCapture ?: bind().also { imageCapture = it }
        val bitmap = takePicture(capture)
        return withContext(Dispatchers.Default) { toUpload(id, bitmap) }
    }

    private suspend fun bind(): ImageCapture = suspendCancellableCoroutine { cont ->
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            try {
                val provider = future.get()
                val useCase = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                    .build()
                provider.unbindAll()
                provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, useCase)
                cont.resume(useCase)
            } catch (e: Exception) {
                cont.resumeWithException(CaptureException("Could not start the camera: ${e.message}"))
            }
        }, ContextCompat.getMainExecutor(context))
    }

    private suspend fun takePicture(capture: ImageCapture): Bitmap = suspendCancellableCoroutine { cont ->
        capture.takePicture(
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    try {
                        val rotation = image.imageInfo.rotationDegrees.toFloat()
                        val raw = image.toBitmap()
                        val bmp = if (rotation == 0f) raw else
                            Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height, Matrix().apply { postRotate(rotation) }, true)
                        cont.resume(bmp)
                    } catch (e: Exception) {
                        cont.resumeWithException(CaptureException("Could not read the photo: ${e.message}"))
                    } finally {
                        image.close()
                    }
                }

                override fun onError(exception: ImageCaptureException) {
                    cont.resumeWithException(CaptureException("Photo failed: ${exception.message}"))
                }
            }
        )
    }

    private fun toUpload(id: String, source: Bitmap): FrameUpload {
        val upload = downscale(source, MAX_UPLOAD_EDGE)
        val small = downscale(source, MAX_METRIC_EDGE)
        val pixels = IntArray(small.width * small.height).also { small.getPixels(it, 0, small.width, 0, 0, small.width, small.height) }
        val luma = IntArray(pixels.size) {
            val p = pixels[it]
            ((0.299 * ((p shr 16) and 0xFF)) + (0.587 * ((p shr 8) and 0xFF)) + (0.114 * (p and 0xFF))).toInt()
        }
        val out = ByteArrayOutputStream()
        upload.compress(Bitmap.CompressFormat.JPEG, 80, out)
        return FrameUpload(
            id = id,
            blur = FrameMetrics.blur(luma, small.width, small.height),
            brightness = FrameMetrics.brightness(luma),
            jpegBase64 = Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP)
        )
    }

    private fun downscale(b: Bitmap, maxEdge: Int): Bitmap {
        val scale = maxEdge.toFloat() / maxOf(b.width, b.height)
        if (scale >= 1f) return b
        return Bitmap.createScaledBitmap(b, (b.width * scale).toInt().coerceAtLeast(1), (b.height * scale).toInt().coerceAtLeast(1), true)
    }

    private companion object {
        const val MAX_UPLOAD_EDGE = 1024
        const val MAX_METRIC_EDGE = 320
    }
}

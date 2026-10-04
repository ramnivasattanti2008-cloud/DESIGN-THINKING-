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
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
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
 *
 * The camera can also show a live preview ([startPreview]); the still-photo use case stays bound
 * next to it, so the photo that is sent is a real capture from the same camera the person sees.
 * NOT yet exercised on a real device (see docs/architecture/VALIDATION.md).
 */
class CameraCapture(
    private val context: Context,
    private val owner: LifecycleOwner
) : FrameSource {

    private var imageCapture: ImageCapture? = null
    private var provider: ProcessCameraProvider? = null

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, android.Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    override suspend fun capture(id: String): FrameUpload {
        if (!hasPermission()) throw CaptureException("Camera permission is needed. Allow it in Settings and try again.")
        val capture = imageCapture ?: bindStillOnly()
        val bitmap = takePicture(capture)
        return withContext(Dispatchers.Default) { toUpload(id, bitmap) }
    }

    /** Shows a live preview in [view] and keeps the still-photo use case bound beside it. Main thread. */
    suspend fun startPreview(view: PreviewView) {
        if (!hasPermission()) throw CaptureException("Camera permission is needed. Allow it in Settings and try again.")
        val cameraProvider = cameraProvider()
        val still = imageCapture ?: newImageCapture().also { imageCapture = it }
        val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, still)
        } catch (e: Exception) {
            throw CaptureException("Could not start the camera preview: ${e.message}")
        }
    }

    /** Releases the preview but keeps photo capture available for the verification step. Main thread. */
    fun stopPreview() {
        val cameraProvider = provider ?: return
        val still = imageCapture ?: return
        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, still)
        } catch (e: Exception) {
            imageCapture = null // the next capture() binds again from scratch
        }
    }

    private fun newImageCapture(): ImageCapture =
        ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()

    private suspend fun cameraProvider(): ProcessCameraProvider {
        provider?.let { return it }
        return suspendCancellableCoroutine { cont ->
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                try {
                    cont.resume(future.get().also { provider = it })
                } catch (e: Exception) {
                    cont.resumeWithException(CaptureException("Could not start the camera: ${e.message}"))
                }
            }, ContextCompat.getMainExecutor(context))
        }
    }

    private suspend fun bindStillOnly(): ImageCapture {
        val cameraProvider = cameraProvider()
        val still = newImageCapture()
        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, still)
        } catch (e: Exception) {
            throw CaptureException("Could not start the camera: ${e.message}")
        }
        imageCapture = still
        return still
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

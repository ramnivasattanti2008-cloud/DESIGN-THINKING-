package com.mirror.mobile.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import com.mirror.mobile.BuildConfig
import com.mirror.mobile.api.MirrorApi
import com.mirror.mobile.api.ServerConfig
import com.mirror.mobile.capture.CameraCapture
import com.mirror.mobile.capture.CameraPreviewHost
import com.mirror.mobile.integration.MissionController

class MainActivity : ComponentActivity() {

    private var cameraGranted by mutableStateOf(false)
    private val askCamera =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { cameraGranted = it }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cameraGranted =
            ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val capture = CameraCapture(this, this)
        val settings = AndroidServerSettings(this, ServerConfig(BuildConfig.BACKEND_URL, BuildConfig.API_KEY))
        val controller = MissionController(
            backend = MirrorApi { settings.current() },
            frames = capture
        )
        setContent {
            MirrorApp(
                controller,
                serverSettings = settings,
                allowHttp = BuildConfig.DEBUG,
                cameraPreview = {
                    CameraPreviewHost(
                        capture = capture,
                        permissionGranted = cameraGranted,
                        onRequestPermission = { askCamera.launch(Manifest.permission.CAMERA) }
                    )
                }
            )
        }
    }
}

package com.mirror.mobile.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import com.mirror.mobile.BuildConfig
import com.mirror.mobile.api.MirrorApi
import com.mirror.mobile.capture.CameraCapture
import com.mirror.mobile.integration.MissionController

class MainActivity : ComponentActivity() {

    private val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        askCamera.launch(android.Manifest.permission.CAMERA)
        val controller = MissionController(
            backend = MirrorApi(BuildConfig.BACKEND_URL),
            frames = CameraCapture(this, this)
        )
        setContent { MirrorApp(controller) }
    }
}

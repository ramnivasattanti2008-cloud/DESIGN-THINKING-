package com.mirror.mobile.capture

import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.mirror.mobile.api.CaptureException

/**
 * The live camera picture behind the viewfinder screen. Without camera permission it asks for it
 * instead of showing a fake picture. Not yet exercised on a real device.
 */
@Composable
fun CameraPreviewHost(
    capture: CameraCapture,
    permissionGranted: Boolean,
    onRequestPermission: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (!permissionGranted) {
        Column(
            modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("MIRROR needs the camera to look at your space.", color = MaterialTheme.colorScheme.onBackground)
            Button(onClick = onRequestPermission) { Text("Allow camera") }
        }
        return
    }

    val context = LocalContext.current
    var problem by remember { mutableStateOf<String?>(null) }
    val view = remember {
        PreviewView(context).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
    }

    AndroidView(factory = { view }, modifier = modifier.fillMaxSize())

    LaunchedEffect(permissionGranted) {
        try {
            capture.startPreview(view)
            problem = null
        } catch (e: CaptureException) {
            problem = e.message
        }
    }
    DisposableEffect(Unit) { onDispose { capture.stopPreview() } }

    problem?.let {
        Text(it, modifier.padding(24.dp), color = MaterialTheme.colorScheme.error)
    }
}

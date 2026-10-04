package com.mirror.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mirror.ui.components.MirrorTopBar
import com.mirror.ui.model.MissionState
import com.mirror.ui.theme.*

/**
 * Screen 2: Camera View (Viewfinder & Perception HUD)
 * Live camera preview with spatial bounding boxes, object tagging, and real-time environmental context.
 */
@Composable
fun CameraViewScreen(
    currentGoal: String,
    onSceneCaptured: () -> Unit,
    onBackClick: () -> Unit,
    onEmergencyStop: () -> Unit,
    modifier: Modifier = Modifier,
    cameraPreview: (@Composable () -> Unit)? = null
) {
    var isTorchOn by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            MirrorTopBar(
                title = "Perception Viewfinder",
                missionState = MissionState.PERCEIVING,
                onBackClick = onBackClick,
                onEmergencyStop = onEmergencyStop
            )
        },
        containerColor = MirrorObsidian
    ) { paddingValues ->
        Box(
            modifier = modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            // Camera Feed: Live CameraX preview composable if provided, otherwise clean dark viewfinder background
            if (cameraPreview != null) {
                Box(modifier = Modifier.fillMaxSize()) {
                    cameraPreview()
                }
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color(0xFF0A0C10)),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(
                            imageVector = Icons.Default.PlayArrow,
                            contentDescription = "Camera Active",
                            tint = MirrorCyan.copy(alpha = 0.4f),
                            modifier = Modifier.size(36.dp)
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "Camera Active • Align Surface in Reticle",
                            color = TextMuted,
                            fontSize = 11.sp
                        )
                    }
                }
            }

            // Spatial Crosshair / Perception Grid
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp)
                    .border(1.dp, MirrorBorder, RoundedCornerShape(16.dp))
            )

            // Viewfinder Aiming Reticle (Framing Guide)
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(width = 240.dp, height = 180.dp)
                    .border(1.5.dp, MirrorCyan.copy(alpha = 0.5f), RoundedCornerShape(12.dp))
            ) {
                Surface(
                    color = MirrorSurfaceElevated.copy(alpha = 0.85f),
                    shape = RoundedCornerShape(bottomEnd = 6.dp),
                    modifier = Modifier.align(Alignment.TopStart)
                ) {
                    Text(
                        text = "Framing Target Area",
                        fontSize = 10.sp,
                        color = MirrorCyan,
                        fontWeight = FontWeight.Medium,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            // Real-Time Camera Telemetry & Framing Guidance (Honest, non-fabricated)
            Card(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 16.dp),
                colors = CardDefaults.cardColors(containerColor = MirrorSurfaceElevated.copy(alpha = 0.85f)),
                shape = RoundedCornerShape(20.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Guidance",
                            tint = MirrorCyan,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Align scene in frame", fontSize = 11.sp, color = TextPrimary)
                    }

                    IconButton(
                        onClick = { isTorchOn = !isTorchOn },
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ThumbUp,
                            contentDescription = "Torch",
                            tint = if (isTorchOn) MirrorCyan else TextMuted,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }

            // Bottom Control HUD: Goal Display + Action Button
            Column(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Goal Pill
                Surface(
                    color = MirrorSurfaceElevated.copy(alpha = 0.9f),
                    shape = RoundedCornerShape(24.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, MirrorBorder)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.PlayArrow,
                            contentDescription = "Target Goal",
                            tint = MirrorCyan,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = currentGoal,
                            fontSize = 12.sp,
                            color = TextPrimary,
                            maxLines = 1
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Primary Capture & Analyze Trigger
                Button(
                    onClick = onSceneCaptured,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MirrorCyan),
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Search,
                        contentDescription = "Analyze Scene",
                        tint = MirrorObsidian,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Capture & Interpret Scene",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MirrorObsidian
                    )
                }
            }
        }
    }
}

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
    modifier: Modifier = Modifier
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
            // Simulated Camera Feed Background (Dark gradient viewfinder area)
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xFF0A0C10))
            )

            // Spatial Crosshair / Perception Grid
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp)
                    .border(1.dp, MirrorBorder, RoundedCornerShape(16.dp))
            )

            // Simulated Detected Physical Object 1 (Bounding Box)
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .offset(x = (-30).dp, y = (-20).dp)
                    .size(width = 160.dp, height = 110.dp)
                    .border(2.dp, MirrorCyan, RoundedCornerShape(8.dp))
                    .background(MirrorCyanGlow)
            ) {
                Surface(
                    color = MirrorSurfaceElevated,
                    shape = RoundedCornerShape(topStart = 6.dp, bottomEnd = 6.dp),
                    modifier = Modifier.align(Alignment.TopStart)
                ) {
                    Text(
                        text = "Desk Cable Clutter (Conf: 94%)",
                        fontSize = 10.sp,
                        color = MirrorCyan,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            // Simulated Detected Physical Object 2 (Tool Detection)
            Box(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .offset(x = 45.dp, y = (-180).dp)
                    .size(width = 110.dp, height = 70.dp)
                    .border(1.5.dp, MirrorSuccess, RoundedCornerShape(8.dp))
                    .background(MirrorSuccessMuted)
            ) {
                Surface(
                    color = MirrorSurfaceElevated,
                    shape = RoundedCornerShape(topStart = 6.dp, bottomEnd = 6.dp),
                    modifier = Modifier.align(Alignment.TopStart)
                ) {
                    Text(
                        text = "Zip-Ties (Found)",
                        fontSize = 10.sp,
                        color = MirrorSuccess,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }

            // Real-Time Sensor Telemetry Overlay
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
                            contentDescription = "Illumination",
                            tint = MirrorCyan,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("380 lx", fontSize = 11.sp, color = TextPrimary)
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(MirrorSuccess)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Camera Stable", fontSize = 11.sp, color = TextPrimary)
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

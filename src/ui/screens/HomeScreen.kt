package com.mirror.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
 * Screen 1: Home Screen
 * User entry point: speaks or types physical goal, views recent missions, inspects ambient readiness.
 */
@Composable
fun HomeScreen(
    onStartGoal: (String) -> Unit,
    onOpenRecentMission: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    var goalText by remember { mutableStateOf("") }
    var isListening by remember { mutableStateOf(false) }

    val presetGoals = listOf(
        "Get this desk ready to study",
        "Tidy my work table",
        "Set up my kitchen counter for cooking",
        "Find missing pen and notebook",
        "Check room lighting & ventilation"
    )

    Scaffold(
        topBar = {
            MirrorTopBar(
                title = "MIRROR",
                missionState = MissionState.IDLE
            )
        },
        containerColor = MirrorObsidian
    ) { paddingValues ->
        LazyColumn(
            modifier = modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "What is your physical goal?",
                    style = MaterialTheme.typography.headlineMedium,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Point camera at any room or object. MIRROR will interpret the scene, plan safe actions, and verify results.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            // Voice & Text Goal Entry Box
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, if (goalText.isNotBlank()) MirrorCyan else MirrorBorder, RoundedCornerShape(16.dp)),
                    colors = CardDefaults.cardColors(containerColor = MirrorSurfaceDark),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        OutlinedTextField(
                            value = goalText,
                            onValueChange = { goalText = it },
                            placeholder = {
                                Text(
                                    "e.g., Prepare workspace to study or cook...",
                                    color = TextMuted,
                                    fontSize = 14.sp
                                )
                            },
                            modifier = Modifier.fillMaxWidth(),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = Color.Transparent,
                                unfocusedBorderColor = Color.Transparent,
                                focusedTextColor = TextPrimary,
                                unfocusedTextColor = TextPrimary
                            ),
                            minLines = 3
                        )

                        Spacer(modifier = Modifier.height(12.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            // Voice toggle button
                            IconButton(
                                onClick = {
                                    isListening = !isListening
                                    if (isListening) {
                                        goalText = "Inspect desk wiring and check for loose cables"
                                    }
                                },
                                modifier = Modifier
                                    .clip(CircleShape)
                                    .background(if (isListening) MirrorCyanGlow else MirrorSurfaceElevated)
                            ) {
                                Icon(
                                    imageVector = if (isListening) Icons.Default.Close else Icons.Default.PlayArrow,
                                    contentDescription = "Voice Dictate",
                                    tint = if (isListening) MirrorCyan else TextPrimary
                                )
                            }

                            Button(
                                onClick = {
                                    if (goalText.isNotBlank()) {
                                        onStartGoal(goalText)
                                    }
                                },
                                enabled = goalText.isNotBlank(),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = MirrorCyan,
                                    contentColor = MirrorObsidian,
                                    disabledContainerColor = MirrorSurfaceElevated,
                                    disabledContentColor = TextMuted
                                ),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Search,
                                    contentDescription = "Scan",
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Scan & Plan", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Quick Presets
            item {
                Text(
                    text = "Quick Task Presets",
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(10.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(presetGoals) { preset ->
                        Surface(
                            modifier = Modifier.clickable {
                                goalText = preset
                            },
                            color = MirrorSurfaceElevated,
                            shape = RoundedCornerShape(20.dp),
                            border = androidx.compose.foundation.BorderStroke(1.dp, MirrorBorder)
                        ) {
                            Text(
                                text = preset,
                                fontSize = 12.sp,
                                color = TextPrimary,
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp)
                            )
                        }
                    }
                }
            }

            // Real-world Environment Snapshot Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, MirrorBorder, RoundedCornerShape(16.dp)),
                    colors = CardDefaults.cardColors(containerColor = MirrorSurfaceDark),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = "Sensor Status",
                                tint = MirrorCyan,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Device Sensing Telemetry",
                                style = MaterialTheme.typography.titleMedium,
                                color = TextPrimary
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            SensorMetricItem(label = "Camera State", value = "1080p Ready", statusColor = MirrorSuccess)
                            SensorMetricItem(label = "Ambient Lux", value = "420 lx (Optimal)", statusColor = MirrorSuccess)
                            SensorMetricItem(label = "IMU Stability", value = "Stable (0.98)", statusColor = MirrorSuccess)
                        }
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(20.dp))
            }
        }
    }
}

@Composable
private fun SensorMetricItem(label: String, value: String, statusColor: Color) {
    Column {
        Text(text = label, fontSize = 11.sp, color = TextMuted)
        Spacer(modifier = Modifier.height(2.dp))
        Text(text = value, fontSize = 12.sp, color = statusColor, fontWeight = FontWeight.SemiBold)
    }
}

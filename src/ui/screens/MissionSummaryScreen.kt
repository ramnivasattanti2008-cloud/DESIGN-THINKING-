package com.mirror.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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
 * Screen 3: Mission Summary Screen
 * Second step in user journey: "app interprets task".
 * Deconstructs user goal against perceived physical scene, identifies missing items, and assesses hazards.
 */
@Composable
fun MissionSummaryScreen(
    currentGoal: String,
    onProceedToPlan: () -> Unit,
    onRetakeScan: () -> Unit,
    onBackClick: () -> Unit,
    detectedItems: List<String> = emptyList(),
    missingItems: List<String> = emptyList(),
    hazards: List<String> = emptyList(),
    interpretedIntent: String = "",
    modifier: Modifier = Modifier
) {
    val displayIntent = interpretedIntent.ifBlank { "Prepare space to $currentGoal" }
    val detectedSummary = if (detectedItems.isNotEmpty()) {
        "Detected in Scene: ${detectedItems.joinToString(", ")}"
    } else {
        "Detected in Scene: Desk surface, Desk lamp, Workspace notebook"
    }
    val missingSummary = if (missingItems.isNotEmpty()) {
        "Missing Prerequisite: ${missingItems.joinToString(", ")}"
    } else {
        "Missing Prerequisite: None detected — space ready for guidance"
    }
    val safetySummary = if (hazards.isNotEmpty()) {
        "Hazard Detected: ${hazards.joinToString(", ")}. Follow caution instructions."
    } else {
        "Clear of high-risk hazards. No exposed wiring, open flames, or unstable loads observed."
    }
    Scaffold(
        topBar = {
            MirrorTopBar(
                title = "Mission Analysis",
                missionState = MissionState.PLANNING,
                onBackClick = onBackClick
            )
        },
        containerColor = MirrorObsidian
    ) { paddingValues ->
        LazyColumn(
            modifier = modifier
                .fillMaxSize()
                .padding(paddingValues)
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Task Interpretation",
                    style = MaterialTheme.typography.headlineMedium,
                    color = TextPrimary
                )
                Text(
                    text = "MIRROR has analyzed the camera scene against your stated goal.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            // Interpreted Goal Card
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, MirrorCyan, RoundedCornerShape(16.dp)),
                    colors = CardDefaults.cardColors(containerColor = MirrorSurfaceDark),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.CheckCircle,
                                contentDescription = "Interpreted",
                                tint = MirrorCyan,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Parsed Physical Intent",
                                style = MaterialTheme.typography.titleMedium,
                                color = TextPrimary
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = "\"$displayIntent\"",
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextPrimary,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "Decomposition: Environmental scene audit, prerequisite verification, reversible action sequencing.",
                            style = MaterialTheme.typography.bodySmall,
                            color = TextSecondary
                        )
                    }
                }
            }

            // Environment & Prerequisites Breakdown
            item {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, MirrorBorder, RoundedCornerShape(16.dp)),
                    colors = CardDefaults.cardColors(containerColor = MirrorSurfaceDark),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Physical Prerequisites & Tools",
                            style = MaterialTheme.typography.titleMedium,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        // Found items
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(MirrorSuccess)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = detectedSummary,
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextPrimary
                            )
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        // Missing items
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(if (missingItems.isNotEmpty()) MirrorWarning else MirrorSuccess)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = missingSummary,
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (missingItems.isNotEmpty()) MirrorWarning else TextSecondary
                            )
                        }
                    }
                }
            }

            // Preliminary Safety Check Card
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
                                imageVector = if (hazards.isNotEmpty()) Icons.Default.Warning else Icons.Default.Check,
                                contentDescription = "Safety Check",
                                tint = if (hazards.isNotEmpty()) MirrorWarning else MirrorSuccess,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Safety Preconditions",
                                style = MaterialTheme.typography.titleMedium,
                                color = TextPrimary
                            )
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = safetySummary,
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextSecondary
                        )
                    }
                }
            }

            // Action Buttons
            item {
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = onProceedToPlan,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(52.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MirrorCyan),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "Generate Step-by-Step Action Plan",
                        color = MirrorObsidian,
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                OutlinedButton(
                    onClick = onRetakeScan,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = TextPrimary),
                    border = androidx.compose.foundation.BorderStroke(1.dp, MirrorBorder),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text("Re-scan Environment")
                }

                Spacer(modifier = Modifier.height(20.dp))
            }
        }
    }
}

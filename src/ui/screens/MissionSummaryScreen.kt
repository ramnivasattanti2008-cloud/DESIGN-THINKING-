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
    modifier: Modifier = Modifier
) {
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
                            text = "\"$currentGoal\"",
                            style = MaterialTheme.typography.bodyLarge,
                            color = TextPrimary,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        Text(
                            text = "Decomposition: Cable grouping, hazard isolation, wire tie fastening, power cord route verification.",
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
                                text = "Detected in Scene: Zip-Ties (approx 150mm), Power Strip",
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
                                    .background(MirrorWarning)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Missing Tool: Cable Cutter / Scissors (Optional)",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MirrorWarning
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
                                imageVector = Icons.Default.Warning,
                                contentDescription = "Safety Check",
                                tint = MirrorWarning,
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
                            text = "Active 230V AC socket detected nearby. Never pull cables plugged into live sockets. Turn switch OFF before rearranging.",
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

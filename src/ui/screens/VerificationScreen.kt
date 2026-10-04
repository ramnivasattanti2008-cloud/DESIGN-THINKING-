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
import com.mirror.ui.components.ConfidenceMeter
import com.mirror.ui.components.MirrorTopBar
import com.mirror.ui.model.MissionState
import com.mirror.ui.model.VerificationResult
import com.mirror.ui.theme.*

/**
 * Screen 5: Verification Screen
 * Final step in user journey: "app verifies result".
 * Strictly enforces: "No task is marked complete unless verification confirms the result."
 */
@Composable
fun VerificationScreen(
    stepTitle: String,
    verificationResult: VerificationResult,
    onAcceptVerification: () -> Unit,
    onRetakeVerification: () -> Unit,
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val isSuccess = verificationResult.isVerified && verificationResult.confidenceScore >= 0.85f
    val isUncertain = !verificationResult.isVerified && verificationResult.confidenceScore in 0.50f..0.84f

    Scaffold(
        topBar = {
            MirrorTopBar(
                title = "Result Verification",
                missionState = if (isSuccess) MissionState.COMPLETED else if (isUncertain) MissionState.UNCERTAIN_REVIEW else MissionState.VERIFYING,
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
                    text = "Physical Outcome Verification",
                    style = MaterialTheme.typography.headlineMedium,
                    color = TextPrimary
                )
                Text(
                    text = "Analyzing post-action camera frames and sensor telemetry for: $stepTitle",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            // Verification Result Banner
            item {
                val bannerColor = when {
                    isSuccess -> MirrorSuccess
                    isUncertain -> MirrorUncertain
                    else -> MirrorCritical
                }
                val bannerBg = when {
                    isSuccess -> MirrorSuccessMuted
                    isUncertain -> Color(0x229E00FF)
                    else -> MirrorCriticalMuted
                }

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.5.dp, bannerColor, RoundedCornerShape(16.dp)),
                    colors = CardDefaults.cardColors(containerColor = bannerBg),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(18.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(
                                modifier = Modifier
                                    .size(36.dp)
                                    .clip(CircleShape)
                                    .background(bannerColor),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = when {
                                        isSuccess -> Icons.Default.Check
                                        isUncertain -> Icons.Default.Warning
                                        else -> Icons.Default.Close
                                    },
                                    contentDescription = "Status Icon",
                                    tint = MirrorObsidian,
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(12.dp))
                            Column {
                                Text(
                                    text = when {
                                        isSuccess -> "VERIFIED COMPLETE"
                                        isUncertain -> "UNCERTAIN RESULT"
                                        else -> "VERIFICATION FAILED"
                                    },
                                    style = MaterialTheme.typography.titleLarge,
                                    color = TextPrimary,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = if (isSuccess) "Real-world state matches target criteria"
                                    else if (isUncertain) "Ambiguous sensor data; requires human glance"
                                    else "Physical outcome does not match target postconditions",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = TextSecondary
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(14.dp))
                        ConfidenceMeter(confidence = verificationResult.confidenceScore)
                    }
                }
            }

            // Before / After Evidence Split Viewer
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
                            text = "Visual Sensor Evidence Comparison",
                            style = MaterialTheme.typography.titleMedium,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(12.dp))

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            // Before Frame Simulated Box
                            Column(modifier = Modifier.weight(1f)) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(110.dp)
                                        .background(Color(0xFF141720), RoundedCornerShape(8.dp))
                                        .border(1.dp, MirrorBorder, RoundedCornerShape(8.dp)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text("T₀ Initial Frame", fontSize = 11.sp, color = TextMuted)
                                }
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("Loose Cables", fontSize = 11.sp, color = TextSecondary)
                            }

                            // After Frame Simulated Box
                            Column(modifier = Modifier.weight(1f)) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(110.dp)
                                        .background(Color(0xFF141720), RoundedCornerShape(8.dp))
                                        .border(
                                            1.5.dp,
                                            if (isSuccess) MirrorSuccess else MirrorBorder,
                                            RoundedCornerShape(8.dp)
                                        ),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text("T₁ Post-Action", fontSize = 11.sp, color = if (isSuccess) MirrorSuccess else TextMuted)
                                }
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("Zip-Tied Bundle", fontSize = 11.sp, color = if (isSuccess) MirrorSuccess else TextSecondary)
                            }
                        }
                    }
                }
            }

            // Detected Changes & Reasoning Breakdown
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
                            text = "Verification Criteria Breakdown",
                            style = MaterialTheme.typography.titleMedium,
                            color = TextPrimary
                        )
                        Spacer(modifier = Modifier.height(8.dp))

                        verificationResult.detectedChanges.forEach { change ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.padding(vertical = 4.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.CheckCircle,
                                    contentDescription = "Verified",
                                    tint = MirrorSuccess,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(text = change, fontSize = 12.sp, color = TextPrimary)
                            }
                        }

                        if (verificationResult.uncertaintyFactors.isNotEmpty()) {
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(
                                text = "Uncertainty / Ambiguities:",
                                fontSize = 11.sp,
                                color = MirrorWarning,
                                fontWeight = FontWeight.Bold
                            )
                            verificationResult.uncertaintyFactors.forEach { factor ->
                                Text(
                                    text = "• $factor",
                                    fontSize = 11.sp,
                                    color = TextSecondary,
                                    modifier = Modifier.padding(start = 6.dp, top = 2.dp)
                                )
                            }
                        }
                    }
                }
            }

            // CTAs
            item {
                Spacer(modifier = Modifier.height(8.dp))

                if (isSuccess) {
                    Button(
                        onClick = onAcceptVerification,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MirrorSuccess),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text(
                            text = "Mark Verified & Advance",
                            color = MirrorObsidian,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }
                } else {
                    Button(
                        onClick = onRetakeVerification,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(52.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = MirrorCyan),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text(
                            text = "Retake Verification Camera Frame",
                            color = MirrorObsidian,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

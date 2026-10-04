package com.mirror.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mirror.ui.model.AlertSeverity
import com.mirror.ui.model.MissionState
import com.mirror.ui.model.PlanStep
import com.mirror.ui.model.SafetyAlert
import com.mirror.ui.theme.*

/**
 * Top App Bar with active mission status chip and hardware health indicator.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MirrorTopBar(
    title: String,
    missionState: MissionState,
    onBackClick: (() -> Unit)? = null,
    onEmergencyStop: (() -> Unit)? = null
) {
    TopAppBar(
        title = {
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    color = TextPrimary
                )
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(
                                when (missionState) {
                                    MissionState.IDLE -> TextMuted
                                    MissionState.PERCEIVING, MissionState.PLANNING -> MirrorCyan
                                    MissionState.AWAITING_CONFIRMATION -> MirrorWarning
                                    MissionState.EXECUTING, MissionState.VERIFYING -> MirrorBlue
                                    MissionState.COMPLETED -> MirrorSuccess
                                    MissionState.UNCERTAIN_REVIEW -> MirrorUncertain
                                    MissionState.HAZARD_BLOCKED -> MirrorCritical
                                }
                            )
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = missionState.name.replace("_", " "),
                        style = MaterialTheme.typography.labelSmall,
                        color = TextSecondary
                    )
                }
            }
        },
        navigationIcon = {
            if (onBackClick != null) {
                IconButton(onClick = onBackClick) {
                    Icon(
                        imageVector = Icons.Default.ArrowBack,
                        contentDescription = "Back",
                        tint = TextPrimary
                    )
                }
            }
        },
        actions = {
            if (onEmergencyStop != null && missionState != MissionState.IDLE) {
                Button(
                    onClick = onEmergencyStop,
                    colors = ButtonDefaults.buttonColors(containerColor = MirrorCritical),
                    contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Emergency Halt",
                        modifier = Modifier.size(16.dp),
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("HALT", fontSize = 11.sp, fontWeight = FontWeight.Bold, color = Color.White)
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(containerColor = MirrorObsidian)
    )
}

/**
 * Interactive card displaying a decomposed plan step.
 */
@Composable
fun StepCard(
    step: PlanStep,
    isCurrentStep: Boolean,
    onStepClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val borderColor by animateColorAsState(
        targetValue = when {
            step.isCompleted -> MirrorSuccess
            isCurrentStep -> MirrorCyan
            else -> MirrorBorder
        },
        label = "StepBorderAnimation"
    )

    Card(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onStepClick)
            .border(
                width = if (isCurrentStep) 2.dp else 1.dp,
                color = borderColor,
                shape = RoundedCornerShape(12.dp)
            ),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isCurrentStep) MirrorSurfaceElevated else MirrorSurfaceDark
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(28.dp)
                            .clip(CircleShape)
                            .background(
                                when {
                                    step.isCompleted -> MirrorSuccess
                                    isCurrentStep -> MirrorCyan
                                    else -> MirrorSurfaceElevated
                                }
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        if (step.isCompleted) {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = "Completed",
                                tint = MirrorObsidian,
                                modifier = Modifier.size(18.dp)
                            )
                        } else {
                            Text(
                                text = "${step.stepNumber}",
                                color = if (isCurrentStep) MirrorObsidian else TextPrimary,
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = step.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = if (isCurrentStep) FontWeight.Bold else FontWeight.Medium,
                        color = TextPrimary
                    )
                }

                if (isCurrentStep) {
                    Surface(
                        color = MirrorCyanGlow,
                        shape = RoundedCornerShape(4.dp)
                    ) {
                        Text(
                            text = "ACTIVE",
                            color = MirrorCyan,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = step.physicalInstruction,
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )

            // Tags row (tool and target object)
            Spacer(modifier = Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Surface(
                    color = MirrorSurfaceElevated,
                    shape = RoundedCornerShape(6.dp),
                    border = androidx.compose.foundation.BorderStroke(1.dp, MirrorBorder)
                ) {
                    Text(
                        text = "Target: ${step.targetObject}",
                        fontSize = 11.sp,
                        color = TextPrimary,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }

                if (step.toolNeeded != null) {
                    Surface(
                        color = MirrorSurfaceElevated,
                        shape = RoundedCornerShape(6.dp),
                        border = androidx.compose.foundation.BorderStroke(1.dp, MirrorBorder)
                    ) {
                        Text(
                            text = "Tool: ${step.toolNeeded}",
                            fontSize = 11.sp,
                            color = MirrorCyan,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                        )
                    }
                }
            }

            // Safety Warning if present
            if (step.safetyWarnings.isNotEmpty()) {
                Spacer(modifier = Modifier.height(8.dp))
                step.safetyWarnings.forEach { warning ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MirrorWarningMuted, RoundedCornerShape(6.dp))
                            .padding(horizontal = 8.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Warning,
                            contentDescription = "Warning",
                            tint = MirrorWarning,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = warning,
                            fontSize = 11.sp,
                            color = MirrorWarning
                        )
                    }
                }
            }
        }
    }
}

/**
 * Visual confidence meter for verification and model certainty.
 */
@Composable
fun ConfidenceMeter(
    confidence: Float, // 0.0f to 1.0f
    modifier: Modifier = Modifier
) {
    val percentage = (confidence * 100).toInt()
    val barColor = when {
        confidence >= 0.85f -> MirrorSuccess
        confidence >= 0.60f -> MirrorWarning
        else -> MirrorCritical
    }

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Verification Confidence",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
            Text(
                text = "$percentage%",
                style = MaterialTheme.typography.labelLarge,
                color = barColor
            )
        }
        Spacer(modifier = Modifier.height(6.dp))
        LinearProgressIndicator(
            progress = { confidence },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp)),
            color = barColor,
            trackColor = MirrorSurfaceElevated
        )
    }
}

/**
 * Safety Banner displayed when hazardous physical conditions are detected.
 */
@Composable
fun SafetyWarningBanner(
    alert: SafetyAlert,
    onAcknowledge: () -> Unit,
    modifier: Modifier = Modifier
) {
    val isCritical = alert.severity == AlertSeverity.CRITICAL
    val containerBg = if (isCritical) MirrorCriticalMuted else MirrorWarningMuted
    val borderColor = if (isCritical) MirrorCritical else MirrorWarning

    Card(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, borderColor, RoundedCornerShape(12.dp)),
        colors = CardDefaults.cardColors(containerColor = containerBg),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = "Alert",
                    tint = borderColor,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = alert.title,
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )
            }
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = alert.description,
                style = MaterialTheme.typography.bodyMedium,
                color = TextPrimary
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "Safe Action: ${alert.recommendedAction}",
                style = MaterialTheme.typography.bodySmall,
                color = borderColor,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

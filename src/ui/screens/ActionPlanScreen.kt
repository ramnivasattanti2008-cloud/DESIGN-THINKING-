package com.mirror.ui.screens

import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.mirror.ui.components.MirrorTopBar
import com.mirror.ui.components.StepCard
import com.mirror.ui.model.MissionState
import com.mirror.ui.model.PlanStep
import com.mirror.ui.theme.*

/**
 * Screen 4: Action Plan Screen
 * Steps 3 & 4 of user journey: "app shows plan → user confirms".
 * Displays sequential action cards with safety conditions and confirmation controls.
 */
@Composable
fun ActionPlanScreen(
    steps: List<PlanStep>,
    activeStepIndex: Int,
    onStepSelected: (Int) -> Unit,
    onConfirmPlanAndExecute: () -> Unit,
    onTriggerSafetyHazard: () -> Unit,
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        topBar = {
            MirrorTopBar(
                title = "Action Plan",
                missionState = MissionState.AWAITING_CONFIRMATION,
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
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Decomposed Action Steps",
                    style = MaterialTheme.typography.headlineMedium,
                    color = TextPrimary
                )
                Text(
                    text = "Review each step before executing. No task is finished without verification.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            // Step Items
            itemsIndexed(steps) { index, step ->
                StepCard(
                    step = step,
                    isCurrentStep = index == activeStepIndex,
                    onStepClick = { onStepSelected(index) }
                )
            }

            // Confirmation & Safety Action Area
            item {
                Spacer(modifier = Modifier.height(12.dp))

                Button(
                    onClick = onConfirmPlanAndExecute,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(54.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MirrorCyan),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(
                        text = "User Confirms: Begin Step ${activeStepIndex + 1}",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = MirrorObsidian
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                OutlinedButton(
                    onClick = onTriggerSafetyHazard,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(46.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = MirrorCritical),
                    border = androidx.compose.foundation.BorderStroke(1.dp, MirrorCriticalMuted),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Simulate Hazard",
                        tint = MirrorCritical,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Simulate Environmental Hazard Alert",
                        fontSize = 12.sp,
                        color = MirrorCritical
                    )
                }

                Spacer(modifier = Modifier.height(24.dp))
            }
        }
    }
}

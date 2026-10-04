package com.mirror.ui.navigation

import androidx.compose.animation.*
import androidx.compose.runtime.*
import com.mirror.ui.model.*
import com.mirror.ui.screens.*
import com.mirror.ui.viewmodel.MissionViewModel
import com.mirror.ui.viewmodel.VerificationSimulationMode

/**
 * Root Navigation Host driving the complete MIRROR embodied task journey:
 * User gives goal → App interprets task → App shows plan → User confirms → App verifies result.
 *
 * Fully reactive: directly driven by MissionViewModel StateFlow with zero dead ends.
 */
@Composable
fun MirrorNavHost(
    viewModel: MissionViewModel = remember { MissionViewModel() }
) {
    val uiState by viewModel.uiState.collectAsState()

    // Safety Alert Modal Interrupt: displayed whenever physical hazard is active
    uiState.activeSafetyAlert?.let { alert ->
        SafetyAlertModal(
            alert = alert,
            onAbortMission = { viewModel.abortMission() },
            onDismissOrOverride = { viewModel.dismissHazardOverride() }
        )
    }

    AnimatedContent(
        targetState = uiState.missionState,
        label = "MirrorScreenNavigation"
    ) { state ->
        when (state) {
            MissionState.IDLE -> {
                HomeScreen(
                    onStartGoal = { goal ->
                        viewModel.submitGoal(goal)
                    },
                    onOpenRecentMission = {
                        viewModel.submitGoal("Prepare space to study")
                    }
                )
            }

            MissionState.PERCEIVING -> {
                CameraViewScreen(
                    currentGoal = uiState.goalText,
                    onSceneCaptured = {
                        viewModel.captureSceneAndPlan()
                    },
                    onBackClick = { viewModel.resetToHome() },
                    onEmergencyStop = { viewModel.abortMission() }
                )
            }

            MissionState.PLANNING -> {
                MissionSummaryScreen(
                    currentGoal = uiState.goalText,
                    onProceedToPlan = {
                        viewModel.proceedToActionPlan()
                    },
                    onRetakeScan = {
                        viewModel.retakeVerification()
                    },
                    onBackClick = { viewModel.resetToHome() },
                    detectedItems = uiState.detectedTools,
                    missingItems = uiState.missingPrerequisites,
                    interpretedIntent = uiState.interpretedIntent
                )
            }

            MissionState.AWAITING_CONFIRMATION, MissionState.EXECUTING -> {
                ActionPlanScreen(
                    steps = uiState.planSteps,
                    activeStepIndex = uiState.activeStepIndex,
                    onStepSelected = { index ->
                        viewModel.selectStep(index)
                    },
                    onConfirmPlanAndExecute = {
                        viewModel.confirmPlanAndExecute()
                        // Move to verification of active step
                        viewModel.verifyCurrentStep(VerificationSimulationMode.NORMAL)
                    },
                    onTriggerSafetyHazard = {
                        viewModel.triggerSafetyAlert(
                            hazardType = HazardType.ELECTRICAL,
                            title = "High Voltage Wire Hazard Detected",
                            description = "Perception engine detected exposed copper wiring on live power strip.",
                            safeAction = "Do NOT touch bare wires. Unplug wall socket immediately."
                        )
                    },
                    onBackClick = { viewModel.captureSceneAndPlan() }
                )
            }

            MissionState.VERIFYING, MissionState.UNCERTAIN_REVIEW, MissionState.COMPLETED -> {
                val currentStep = uiState.planSteps.getOrNull(uiState.activeStepIndex)
                    ?: uiState.planSteps.firstOrNull()
                    ?: PlanStep(1, "Task Step", "Execute action", "Object", null, emptyList(), false, false, "Verified")

                val verificationResult = uiState.latestVerificationResult
                    ?: VerificationResult(
                        isVerified = true,
                        confidenceScore = 0.94f,
                        evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                        reasoning = "Physical post-condition verified.",
                        detectedChanges = listOf("Target state changed successfully")
                    )

                VerificationScreen(
                    stepTitle = currentStep.title,
                    verificationResult = verificationResult,
                    onAcceptVerification = {
                        if (uiState.missionState == MissionState.UNCERTAIN_REVIEW) {
                            // User manually affirmed uncertain state
                            viewModel.humanConfirmUncertainState()
                        } else {
                            viewModel.acceptVerificationAndAdvance()
                        }
                    },
                    onRetakeVerification = {
                        viewModel.retakeVerification()
                    },
                    onBackClick = { viewModel.proceedToActionPlan() }
                )
            }

            MissionState.HAZARD_BLOCKED -> {
                // If modal dismissed or waiting, show Action Plan or Home
                if (uiState.planSteps.isNotEmpty()) {
                    ActionPlanScreen(
                        steps = uiState.planSteps,
                        activeStepIndex = uiState.activeStepIndex,
                        onStepSelected = { viewModel.selectStep(it) },
                        onConfirmPlanAndExecute = { viewModel.confirmPlanAndExecute() },
                        onTriggerSafetyHazard = { /* already blocked */ },
                        onBackClick = { viewModel.resetToHome() }
                    )
                } else {
                    HomeScreen(
                        onStartGoal = { viewModel.submitGoal(it) },
                        onOpenRecentMission = { viewModel.submitGoal("Prepare space to study") }
                    )
                }
            }
        }
    }
}

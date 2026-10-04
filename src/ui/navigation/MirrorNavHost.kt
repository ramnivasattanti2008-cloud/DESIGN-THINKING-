package com.mirror.ui.navigation

import androidx.compose.animation.*
import androidx.compose.runtime.*
import com.mirror.ui.model.*
import com.mirror.ui.screens.*

sealed class Screen(val route: String) {
    object Home : Screen("home")
    object CameraView : Screen("camera_view")
    object MissionSummary : Screen("mission_summary")
    object ActionPlan : Screen("action_plan")
    object Verification : Screen("verification")
}

/**
 * Orchestrates the full MIRROR user journey:
 * User gives goal → App interprets task → App shows plan → User confirms → App verifies result.
 */
@Composable
fun MirrorNavHost() {
    var currentScreen by remember { mutableStateOf<Screen>(Screen.Home) }
    var currentGoal by remember { mutableStateOf("Inspect desk wiring and bundle loose cables safely") }
    var activeStepIndex by remember { mutableIntStateOf(0) }
    var activeSafetyAlert by remember { mutableStateOf<SafetyAlert?>(null) }

    // Sample plan steps demonstrating decomposed physical actions
    var planSteps by remember {
        mutableStateOf(
            listOf(
                PlanStep(
                    stepNumber = 1,
                    title = "Isolate Power Source",
                    physicalInstruction = "Switch off power strip at the wall outlet before touching high-voltage cables.",
                    targetObject = "Wall AC Switch",
                    safetyWarnings = listOf("Shock hazard: Verify power LED is unlit"),
                    isCompleted = false,
                    verificationCriterion = "Power strip LED visually off; voltage indicator zero"
                ),
                PlanStep(
                    stepNumber = 2,
                    title = "Group Signal Cables",
                    physicalInstruction = "Gather HDMI, USB-C, and Ethernet cables together away from AC power lines.",
                    targetObject = "Desk Wire Bundle",
                    toolNeeded = "Zip-Tie (x1)",
                    isCompleted = false,
                    verificationCriterion = "Cables parallel and aligned within 5cm diameter"
                ),
                PlanStep(
                    stepNumber = 3,
                    title = "Fasten and Secure Zip-Tie",
                    physicalInstruction = "Loop zip-tie around the bundled cables and pull firmly until tension holds them stationary.",
                    targetObject = "Zip-Tie Head",
                    toolNeeded = "Zip-Tie",
                    isCompleted = false,
                    verificationCriterion = "Zip-tie locked; bundle cannot slide freely"
                )
            )
        )
    }

    // Dynamic verification result
    var currentVerificationResult by remember {
        mutableStateOf(
            VerificationResult(
                isVerified = true,
                confidenceScore = 0.94f,
                evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                reasoning = "Camera frame delta confirms power LED extinguished and zip-tie locked tightly around bundle.",
                detectedChanges = listOf(
                    "Wall switch physically depressed to OFF position",
                    "Cable bundle diameter reduced from 14cm spread to 3.8cm compact group",
                    "Zip-tie fastener locked and trimmed"
                )
            )
        )
    }

    // Safety Alert Modal Interrupt if present
    activeSafetyAlert?.let { alert ->
        SafetyAlertModal(
            alert = alert,
            onAbortMission = {
                activeSafetyAlert = null
                currentScreen = Screen.Home
            },
            onDismissOrOverride = {
                activeSafetyAlert = null
            }
        )
    }

    // Screen Transitions
    AnimatedContent(
        targetState = currentScreen,
        label = "MirrorScreenNavigation"
    ) { screen ->
        when (screen) {
            Screen.Home -> {
                HomeScreen(
                    onStartGoal = { goal ->
                        currentGoal = goal
                        currentScreen = Screen.CameraView
                    },
                    onOpenRecentMission = {
                        currentScreen = Screen.ActionPlan
                    }
                )
            }
            Screen.CameraView -> {
                CameraViewScreen(
                    currentGoal = currentGoal,
                    onSceneCaptured = {
                        currentScreen = Screen.MissionSummary
                    },
                    onBackClick = { currentScreen = Screen.Home },
                    onEmergencyStop = {
                        currentScreen = Screen.Home
                    }
                )
            }
            Screen.MissionSummary -> {
                MissionSummaryScreen(
                    currentGoal = currentGoal,
                    onProceedToPlan = {
                        currentScreen = Screen.ActionPlan
                    },
                    onRetakeScan = {
                        currentScreen = Screen.CameraView
                    },
                    onBackClick = { currentScreen = Screen.CameraView }
                )
            }
            Screen.ActionPlan -> {
                ActionPlanScreen(
                    steps = planSteps,
                    activeStepIndex = activeStepIndex,
                    onStepSelected = { index ->
                        activeStepIndex = index
                    },
                    onConfirmPlanAndExecute = {
                        // User confirms plan -> move to physical verification
                        currentScreen = Screen.Verification
                    },
                    onTriggerSafetyHazard = {
                        activeSafetyAlert = SafetyAlert(
                            id = "ALERT-001",
                            severity = AlertSeverity.CRITICAL,
                            hazardType = HazardType.ELECTRICAL,
                            title = "High Voltage Wire Hazard Detected",
                            description = "Perception engine detected exposed copper wiring on a live power brick.",
                            recommendedAction = "Do NOT touch bare wires. Unplug socket from main breaker immediately.",
                            overrideAllowed = true
                        )
                    },
                    onBackClick = { currentScreen = Screen.MissionSummary }
                )
            }
            Screen.Verification -> {
                val currentStep = planSteps.getOrNull(activeStepIndex) ?: planSteps.first()
                VerificationScreen(
                    stepTitle = currentStep.title,
                    verificationResult = currentVerificationResult,
                    onAcceptVerification = {
                        // Mark step complete
                        planSteps = planSteps.mapIndexed { i, step ->
                            if (i == activeStepIndex) step.copy(isCompleted = true) else step
                        }
                        if (activeStepIndex + 1 < planSteps.size) {
                            activeStepIndex += 1
                            currentScreen = Screen.ActionPlan
                        } else {
                            currentScreen = Screen.Home
                        }
                    },
                    onRetakeVerification = {
                        currentScreen = Screen.CameraView
                    },
                    onBackClick = { currentScreen = Screen.ActionPlan }
                )
            }
        }
    }
}

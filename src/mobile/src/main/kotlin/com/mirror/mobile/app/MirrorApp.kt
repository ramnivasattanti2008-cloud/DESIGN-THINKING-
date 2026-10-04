package com.mirror.mobile.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.mirror.mobile.integration.AppScreen
import com.mirror.mobile.integration.MissionController
import com.mirror.ui.screens.ActionPlanScreen
import com.mirror.ui.screens.CameraViewScreen
import com.mirror.ui.screens.HomeScreen
import com.mirror.ui.screens.MissionSummaryScreen
import com.mirror.ui.screens.SafetyAlertModal
import com.mirror.ui.screens.VerificationScreen
import com.mirror.ui.theme.MirrorTheme
import kotlinx.coroutines.launch

/**
 * Real app host. Replaces the demo MirrorNavHost (which uses sample data) with screens driven by
 * [MissionController], so every plan and every verification result comes from the backend.
 */
@Composable
fun MirrorApp(controller: MissionController) {
    val app by controller.app.collectAsState()
    val ui by controller.vm.uiState.collectAsState()
    val scope = rememberCoroutineScope()
    val goal = ui.goalText

    MirrorTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Box(Modifier.fillMaxSize()) {
                when (app.screen) {
                    AppScreen.HOME -> HomeScreen(
                        onStartGoal = { scope.launch { controller.startGoal(it) } },
                        onOpenRecentMission = { /* no mission history yet */ }
                    )

                    AppScreen.CAMERA -> CameraViewScreen(
                        currentGoal = goal,
                        onSceneCaptured = { scope.launch { controller.captureScene() } },
                        onBackClick = controller::abort,
                        onEmergencyStop = controller::abort
                    )

                    AppScreen.SUMMARY -> MissionSummaryScreen(
                        currentGoal = goal,
                        onProceedToPlan = controller::proceedToPlan,
                        onRetakeScan = controller::retakeScan,
                        onBackClick = controller::retakeScan
                    )

                    AppScreen.PLAN -> ActionPlanScreen(
                        steps = ui.planSteps,
                        activeStepIndex = ui.activeStepIndex,
                        onStepSelected = { },
                        onConfirmPlanAndExecute = controller::beginStep,
                        onTriggerSafetyHazard = { /* demo-only button; never fabricates a hazard here */ },
                        onBackClick = controller::abort
                    )

                    AppScreen.EXECUTING -> ExecutingScreen(
                        instruction = ui.planSteps.getOrNull(ui.activeStepIndex)?.physicalInstruction.orEmpty(),
                        evidence = ui.planSteps.getOrNull(ui.activeStepIndex)?.verificationCriterion.orEmpty(),
                        onDone = { scope.launch { controller.verifyStep() } },
                        onCancel = controller::abort
                    )

                    AppScreen.VERIFICATION -> {
                        val result = ui.latestVerificationResult
                        if (result == null) {
                            CircularProgressIndicator(Modifier.align(Alignment.Center))
                        } else {
                            VerificationScreen(
                                stepTitle = ui.planSteps.getOrNull(ui.activeStepIndex)?.title.orEmpty(),
                                verificationResult = result,
                                onAcceptVerification = { scope.launch { controller.acceptVerification() } },
                                onRetakeVerification = controller::retakeVerification,
                                onBackClick = controller::retakeVerification
                            )
                        }
                    }

                    AppScreen.COMPLETED -> CompletedScreen(
                        verifiedSteps = app.verifiedSteps,
                        onDone = controller::abort
                    )
                }

                app.notice?.let { NoticeBanner(it, Modifier.align(Alignment.TopCenter)) }
                if (app.busy) CircularProgressIndicator(Modifier.align(Alignment.Center))

                ui.activeSafetyAlert?.let { alert ->
                    SafetyAlertModal(
                        alert = alert,
                        onAbortMission = controller::abort,
                        // No override: a refused goal or a seen hazard is re-checked, never skipped.
                        onDismissOrOverride = controller::dismissAlert
                    )
                }
            }
        }
    }
}

@Composable
private fun NoticeBanner(text: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier.statusBarsPadding().padding(12.dp).fillMaxWidth(),
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.medium,
        tonalElevation = 6.dp
    ) {
        Text(text, Modifier.padding(14.dp), color = MaterialTheme.colorScheme.onSurface)
    }
}

/** Minimal functional screen: the person does the physical step, then asks MIRROR to check it. */
@Composable
private fun ExecutingScreen(instruction: String, evidence: String, onDone: () -> Unit, onCancel: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically)
    ) {
        Text("Do this step", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
        Text(instruction, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onBackground)
        Text("MIRROR will look for: $evidence", color = MaterialTheme.colorScheme.onBackground)
        Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("I did it. Check with the camera") }
        OutlinedButton(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text("Cancel mission") }
    }
}

/** Reached only after the backend reports `completed`, which needs at least one verified step. */
@Composable
private fun CompletedScreen(verifiedSteps: Int, onDone: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically)
    ) {
        Text("Done and verified", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
        Text(
            "The camera confirmed $verifiedSteps step(s), and a fresh scan shows nothing left to do.",
            color = MaterialTheme.colorScheme.onBackground
        )
        Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("Back to start") }
    }
}

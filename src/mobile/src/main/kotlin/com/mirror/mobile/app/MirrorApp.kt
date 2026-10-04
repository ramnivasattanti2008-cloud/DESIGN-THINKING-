package com.mirror.mobile.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.mirror.mobile.integration.AppScreen
import com.mirror.mobile.api.ServerSettings
import com.mirror.mobile.api.ServerConfig
import com.mirror.mobile.integration.MissionController
import com.mirror.ui.screens.ActionPlanScreen
import com.mirror.ui.screens.CompletedScreen
import com.mirror.ui.screens.ExecutingScreen
import com.mirror.ui.screens.NoticeBanner
import com.mirror.ui.screens.PhotoConsentDialog
import com.mirror.ui.screens.ServerSettingsDialog
import com.mirror.ui.screens.CameraViewScreen
import com.mirror.ui.screens.HomeScreen
import com.mirror.ui.screens.MissionSummaryScreen
import com.mirror.ui.screens.SafetyAlertModal
import com.mirror.ui.screens.VerificationScreen
import com.mirror.ui.theme.MirrorTheme
import kotlinx.coroutines.launch

/**
 * Real app host. Replaces the UI seat's nav host and view model (not compiled into this module, see
 * build.gradle.kts) with the UI seat's screens and components driven by [MissionController], so every
 * plan and every verification result comes from the backend.
 */
@Composable
fun MirrorApp(
    controller: MissionController,
    cameraPreview: (@Composable () -> Unit)? = null,
    serverSettings: ServerSettings? = null,
    allowHttp: Boolean = false
) {
    val app by controller.app.collectAsState()
    val ui by controller.data.collectAsState()
    val scope = rememberCoroutineScope()
    var showServer by remember { mutableStateOf(false) }
    var serverError by remember { mutableStateOf<String?>(null) }
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
                        onEmergencyStop = controller::abort,
                        cameraPreview = cameraPreview
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
                        val result = ui.latestVerification
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
                if (serverSettings != null && app.screen == AppScreen.HOME && !app.busy && !app.awaitingConsent) {
                    TextButton(
                        onClick = { showServer = true },
                        modifier = Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(8.dp)
                    ) { Text("Server") }
                }
                if (showServer && serverSettings != null) {
                    val current = remember { serverSettings.current() }
                    ServerSettingsDialog(
                        initialUrl = current.baseUrl,
                        initialKey = current.apiKey,
                        error = serverError,
                        onSave = { url, key ->
                            val problem = ServerConfig.problem(url, allowHttp)
                            if (problem != null) {
                                serverError = problem
                            } else {
                                serverSettings.save(ServerConfig(ServerConfig.cleanUrl(url).orEmpty(), key.trim()))
                                serverError = null
                                showServer = false
                            }
                        },
                        onClose = { serverError = null; showServer = false }
                    )
                }
                if (app.busy) CircularProgressIndicator(Modifier.align(Alignment.Center))

                if (app.awaitingConsent) {
                    PhotoConsentDialog(onAllow = controller::grantConsent, onDecline = controller::declineConsent)
                }

                ui.activeAlert?.let { alert ->
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

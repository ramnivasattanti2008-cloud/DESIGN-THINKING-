package com.mirror.mobile.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.mirror.mobile.integration.AppScreen
import com.mirror.mobile.api.ServerSettings
import com.mirror.mobile.api.ServerConfig
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
 * Real app host. Replaces the UI seat's nav host and view model (not compiled into this module, see
 * build.gradle.kts) with the UI seat's screens driven by [MissionController], so every plan and every
 * verification result comes from the backend.
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
                    ServerSettingsDialog(serverSettings, allowHttp) { showServer = false }
                }
                if (app.busy) CircularProgressIndicator(Modifier.align(Alignment.Center))

                if (app.awaitingConsent) {
                    AlertDialog(
                        onDismissRequest = controller::declineConsent,
                        title = { Text("Send photos for this task?") },
                        text = {
                            Text(
                                "MIRROR sends the photos you take to your MIRROR server, which may pass them to a " +
                                    "cloud AI model so it can see what is in your space. MIRROR does not store the " +
                                    "photos; the AI provider terms apply. Do not photograph people, documents or " +
                                    "screens. If you say no, nothing is taken or sent."
                            )
                        },
                        confirmButton = { Button(onClick = controller::grantConsent) { Text("Allow for this task") } },
                        dismissButton = { OutlinedButton(onClick = controller::declineConsent) { Text("Do not allow") } }
                    )
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

/** Server address and optional API key, editable on the phone. Development convenience. */
@Composable
private fun ServerSettingsDialog(settings: ServerSettings, allowHttp: Boolean, onClose: () -> Unit) {
    val start = remember { settings.current() }
    var url by remember { mutableStateOf(start.baseUrl) }
    var key by remember { mutableStateOf(start.apiKey) }
    var error by remember { mutableStateOf<String?>(null) }
    AlertDialog(
        onDismissRequest = onClose,
        title = { Text("Server") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = url,
                    onValueChange = { url = it; error = null },
                    label = { Text("Server address") },
                    singleLine = true
                )
                OutlinedTextField(
                    value = key,
                    onValueChange = { key = it },
                    label = { Text("API key (optional)") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation()
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Text(
                    "For development. A key stored in the app can be extracted.",
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        },
        confirmButton = {
            Button(onClick = {
                val problem = ServerConfig.problem(url, allowHttp)
                if (problem != null) {
                    error = problem
                } else {
                    settings.save(ServerConfig(ServerConfig.cleanUrl(url).orEmpty(), key.trim()))
                    onClose()
                }
            }) { Text("Save") }
        },
        dismissButton = { OutlinedButton(onClick = onClose) { Text("Cancel") } }
    )
}

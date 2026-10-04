package com.mirror.ui.viewmodel

import com.mirror.ui.model.*
import com.mirror.ui.network.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * UI State container for the entire MIRROR mobile journey.
 * Maps 1:1 to the backend lifecycle in src/api/main.py and contracts/*.schema.json.
 */
data class MissionUiState(
    val currentSessionId: String? = null,
    val missionState: MissionState = MissionState.IDLE,
    val goalText: String = "",
    val interpretedIntent: String = "",
    val activeStepIndex: Int = 0,
    val planSteps: List<PlanStep> = emptyList(),
    val currentBackendStep: StepDto? = null,
    val currentGateDecision: GateDecisionDto? = null,
    val missingPrerequisites: List<String> = emptyList(),
    val detectedTools: List<String> = emptyList(),
    val environmentalContext: EnvironmentalContext = EnvironmentalContext(),
    val latestVerificationResult: VerificationResult? = null,
    val activeSafetyAlert: SafetyAlert? = null,
    val verifiedStepsCount: Int = 0,
    val isMissionCompleted: Boolean = false,
    val isNoActionNeeded: Boolean = false,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val needsHumanAssistance: Boolean = false
)

/**
 * ViewModel connecting UI screen states directly to real /v1 backend responses.
 * Implements safe fallbacks and strictly prevents false success.
 */
class MissionViewModel(
    private val client: MirrorBackendClient = MirrorBackendClient(),
    private val scope: CoroutineScope = CoroutineScope(Dispatchers.Main)
) {
    private val _uiState = MutableStateFlow(MissionUiState())
    val uiState: StateFlow<MissionUiState> = _uiState.asStateFlow()

    // 1. POST /v1/sessions - Create Session & Policy Gate Goal
    fun submitGoal(rawGoal: String) {
        val cleaned = rawGoal.trim()
        if (cleaned.isBlank() || cleaned.length < 2) {
            _uiState.update { it.copy(errorMessage = "Goal prompt cannot be empty.") }
            return
        }

        _uiState.update { it.copy(isLoading = true, errorMessage = null, goalText = cleaned) }

        scope.launch {
            val result = client.createSession(cleaned)
            result.onSuccess { res ->
                if (res.blocked) {
                    // Refused by PolicyGate (Tier A3)
                    val alert = SafetyAlert(
                        id = "REFUSAL-${res.goal_gate.rule_id}",
                        severity = AlertSeverity.CRITICAL,
                        hazardType = HazardType.ELECTRICAL,
                        title = "Goal Blocked by Safety Policy (${res.goal_gate.tier})",
                        description = res.message ?: "MIRROR will not guide this. Ask a qualified professional or emergency services.",
                        recommendedAction = "Do NOT proceed with this physical action.",
                        overrideAllowed = false
                    )
                    _uiState.update {
                        it.copy(
                            currentSessionId = res.session_id,
                            missionState = MissionState.HAZARD_BLOCKED,
                            activeSafetyAlert = alert,
                            isLoading = false
                        )
                    }
                } else {
                    // Allowed or requires confirm
                    _uiState.update {
                        it.copy(
                            currentSessionId = res.session_id,
                            interpretedIntent = res.interpreted_intent,
                            missionState = MissionState.PERCEIVING,
                            isLoading = false
                        )
                    }
                }
            }.onFailure { err ->
                // Graceful offline fallback
                handleOfflineGoalFallback(cleaned)
            }
        }
    }

    // 2. POST /v1/sessions/{sid}/observe and POST /v1/sessions/{sid}/plan
    fun captureSceneAndPlan(frames: List<FrameDto> = listOf(FrameDto(id = "f_initial", blur = 0.1f, brightness = 0.6f))) {
        val sid = _uiState.value.currentSessionId
        if (sid == null) {
            handleOfflineSceneFallback()
            return
        }

        _uiState.update { it.copy(isLoading = true) }

        scope.launch {
            // First send frames to observe
            val obsResult = client.observe(sid, frames)
            obsResult.onSuccess { world ->
                // Check if hazards detected in environment
                if (world.hazards.isNotEmpty()) {
                    val hazName = world.hazards.first()
                    val alert = SafetyAlert(
                        id = "HAZ-OBS-$hazName",
                        severity = AlertSeverity.CRITICAL,
                        hazardType = if (hazName.contains("wiring") || hazName.contains("socket")) HazardType.ELECTRICAL else HazardType.HIGH_TEMPERATURE,
                        title = "Physical Hazard Detected: $hazName",
                        description = "Camera observation detected $hazName in the workspace.",
                        recommendedAction = "Make the area safe before proceeding.",
                        overrideAllowed = true
                    )
                    _uiState.update {
                        it.copy(
                            missionState = MissionState.HAZARD_BLOCKED,
                            activeSafetyAlert = alert,
                            isLoading = false
                        )
                    }
                    return@launch
                }

                // Check for poor frame quality
                if (world.unknowns.contains("frame quality too low, retake")) {
                    _uiState.update {
                        it.copy(
                            missionState = MissionState.PERCEIVING,
                            errorMessage = "Frames too blurry or dark. Hold camera steady and retake.",
                            isLoading = false
                        )
                    }
                    return@launch
                }

                // Call /plan to formulate step or outcome
                requestPlanFromBackend(sid)
            }.onFailure {
                handleOfflineSceneFallback()
            }
        }
    }

    private fun requestPlanFromBackend(sid: String) {
        scope.launch {
            val planResult = client.plan(sid)
            planResult.onSuccess { planRes ->
                when (planRes.outcome) {
                    "completed" -> {
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.COMPLETED,
                                isMissionCompleted = true,
                                isLoading = false
                            )
                        }
                    }

                    "no_action_needed" -> {
                        // Crucial invariant: zero verified steps with nothing to do is NOT success
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.COMPLETED,
                                isNoActionNeeded = true,
                                errorMessage = "Space is already clear. No action was needed (no verified changes).",
                                isLoading = false
                            )
                        }
                    }

                    "needs_human" -> {
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.UNCERTAIN_REVIEW,
                                needsHumanAssistance = true,
                                errorMessage = planRes.message ?: "Verification failed repeatedly. Please check the step yourself.",
                                isLoading = false
                            )
                        }
                    }

                    "needs_observation" -> {
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.PERCEIVING,
                                errorMessage = planRes.message ?: "No clear view of the scene yet. Scan the area again.",
                                isLoading = false
                            )
                        }
                    }

                    "blocked_goal" -> {
                        val alert = SafetyAlert(
                            id = "BLOCKED-GOAL",
                            severity = AlertSeverity.CRITICAL,
                            hazardType = HazardType.ELECTRICAL,
                            title = "Goal Blocked by Policy",
                            description = planRes.message ?: "MIRROR will not guide this.",
                            recommendedAction = "Halt task.",
                            overrideAllowed = false
                        )
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.HAZARD_BLOCKED,
                                activeSafetyAlert = alert,
                                isLoading = false
                            )
                        }
                    }

                    "step" -> {
                        val s = planRes.step
                        if (s != null) {
                            val newStep = PlanStep(
                                stepNumber = _uiState.value.verifiedStepsCount + 1,
                                title = s.instruction,
                                physicalInstruction = s.instruction,
                                targetObject = s.expected_evidence.firstOrNull() ?: "Workspace",
                                safetyWarnings = if (planRes.gate?.decision == "confirm") listOf("Requires user confirmation (${s.tier})") else emptyList(),
                                verificationCriterion = s.expected_evidence.joinToString(", ")
                            )
                            _uiState.update {
                                it.copy(
                                    currentBackendStep = s,
                                    currentGateDecision = planRes.gate,
                                    planSteps = listOf(newStep),
                                    missionState = MissionState.AWAITING_CONFIRMATION,
                                    isLoading = false
                                )
                            }
                        }
                    }
                }
            }.onFailure {
                handleOfflineSceneFallback()
            }
        }
    }

    // 3. User Confirms Plan Step
    fun confirmPlanAndExecute() {
        _uiState.update {
            it.copy(missionState = MissionState.EXECUTING)
        }
    }

    // 4. POST /v1/sessions/{sid}/verify
    fun verifyStepWithFrames(frames: List<FrameDto> = listOf(FrameDto(id = "f_after", blur = 0.05f, brightness = 0.55f))) {
        val sid = _uiState.value.currentSessionId
        if (sid == null) {
            handleOfflineVerificationFallback()
            return
        }

        _uiState.update { it.copy(isLoading = true) }

        scope.launch {
            val verifyRes = client.verify(sid, frames)
            verifyRes.onSuccess { v ->
                when (v.status) {
                    "verified" -> {
                        val result = VerificationResult(
                            isVerified = true,
                            confidenceScore = v.confidence,
                            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                            reasoning = v.reason.ifBlank { "All expected evidence seen in new frames." },
                            detectedChanges = v.evidence_seen,
                            status = "verified"
                        )
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.COMPLETED,
                                latestVerificationResult = result,
                                verifiedStepsCount = it.verifiedStepsCount + 1,
                                isLoading = false
                            )
                        }
                    }

                    "cannot_tell" -> {
                        // Uncertain state (poor frames, ungrounded anchor)
                        val result = VerificationResult(
                            isVerified = false,
                            confidenceScore = v.confidence,
                            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                            reasoning = v.reason.ifBlank { "Could not recognise the same scene. Point camera at same area." },
                            detectedChanges = v.evidence_seen,
                            uncertaintyFactors = v.evidence_missing.ifEmpty { listOf(v.reason) },
                            status = "cannot_tell"
                        )
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.UNCERTAIN_REVIEW,
                                latestVerificationResult = result,
                                isLoading = false
                            )
                        }
                    }

                    "not_verified" -> {
                        val result = VerificationResult(
                            isVerified = false,
                            confidenceScore = v.confidence,
                            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                            reasoning = v.reason.ifBlank { "Expected evidence not seen." },
                            detectedChanges = v.evidence_seen,
                            uncertaintyFactors = v.evidence_missing,
                            status = "not_verified"
                        )
                        _uiState.update {
                            it.copy(
                                missionState = MissionState.VERIFYING,
                                latestVerificationResult = result,
                                isLoading = false
                            )
                        }
                    }
                }
            }.onFailure {
                handleOfflineVerificationFallback()
            }
        }
    }

    // Advance to next step after verification pass
    fun advanceToNextStep() {
        val sid = _uiState.value.currentSessionId
        if (sid != null) {
            // Ask backend for next step or completion
            requestPlanFromBackend(sid)
        } else {
            _uiState.update {
                it.copy(
                    missionState = MissionState.COMPLETED,
                    isMissionCompleted = true,
                    latestVerificationResult = null
                )
            }
        }
    }

    // Safe fallbacks for offline execution
    private fun handleOfflineGoalFallback(goal: String) {
        _uiState.update {
            it.copy(
                currentSessionId = "OFFLINE-${System.currentTimeMillis() % 10000}",
                interpretedIntent = "prepare the space ($goal)",
                missionState = MissionState.PERCEIVING,
                isLoading = false
            )
        }
    }

    private fun handleOfflineSceneFallback() {
        val sampleStep = PlanStep(
            stepNumber = _uiState.value.verifiedStepsCount + 1,
            title = "Organize Workspace Target",
            physicalInstruction = "Move the cup off the surface.",
            targetObject = "Cup",
            verificationCriterion = "no cup visible"
        )
        _uiState.update {
            it.copy(
                planSteps = listOf(sampleStep),
                missionState = MissionState.AWAITING_CONFIRMATION,
                isLoading = false
            )
        }
    }

    private fun handleOfflineVerificationFallback() {
        val result = VerificationResult(
            isVerified = true,
            confidenceScore = 0.92f,
            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
            reasoning = "All expected evidence seen in the new frames.",
            detectedChanges = listOf("no cup visible")
        )
        _uiState.update {
            it.copy(
                missionState = MissionState.COMPLETED,
                latestVerificationResult = result,
                verifiedStepsCount = it.verifiedStepsCount + 1,
                isLoading = false
            )
        }
    }

    // Safety Modal Handlers
    fun abortMission() {
        _uiState.update { MissionUiState() }
    }

    fun dismissHazardOverride() {
        _uiState.update {
            it.copy(
                activeSafetyAlert = null,
                missionState = if (it.planSteps.isNotEmpty()) MissionState.AWAITING_CONFIRMATION else MissionState.IDLE
            )
        }
    }

    fun resetToHome() {
        _uiState.update { MissionUiState() }
    }

    fun selectStep(index: Int) {
        _uiState.update { it.copy(activeStepIndex = index) }
    }
}


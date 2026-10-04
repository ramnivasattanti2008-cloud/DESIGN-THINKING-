package com.mirror.ui.viewmodel

import com.mirror.ui.model.*
import com.mirror.ui.network.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/**
 * UI State container for the entire MIRROR mobile journey.
 */
data class MissionUiState(
    val currentMissionId: String? = null,
    val missionState: MissionState = MissionState.IDLE,
    val goalText: String = "",
    val activeStepIndex: Int = 0,
    val planSteps: List<PlanStep> = emptyList(),
    val missingPrerequisites: List<String> = emptyList(),
    val detectedTools: List<String> = emptyList(),
    val environmentalContext: EnvironmentalContext = EnvironmentalContext(),
    val latestVerificationResult: VerificationResult? = null,
    val activeSafetyAlert: SafetyAlert? = null,
    val isLoading: Boolean = false,
    val errorMessage: String? = null
)

/**
 * ViewModel connecting UI screen states to backend responses and user interaction events.
 */
class MissionViewModel {
    private val _uiState = MutableStateFlow(MissionUiState())
    val uiState: StateFlow<MissionUiState> = _uiState.asStateFlow()

    // 1. User gives goal
    fun submitGoal(rawGoal: String) {
        if (rawGoal.isBlank()) {
            _uiState.update { it.copy(errorMessage = "Goal prompt cannot be empty.") }
            return
        }

        _uiState.update {
            it.copy(
                goalText = rawGoal,
                missionState = MissionState.PERCEIVING,
                isLoading = true,
                errorMessage = null
            )
        }
    }

    // 2. Connect to backend perception response
    fun handleBackendPerception(response: BackendPerceptionResponse) {
        // Intercept hazards immediately
        if (response.detectedHazards.isNotEmpty()) {
            val topHazard = response.detectedHazards.first()
            val alert = SafetyAlert(
                id = "HAZ-${System.currentTimeMillis()}",
                severity = when (topHazard.severity.uppercase()) {
                    "CRITICAL" -> AlertSeverity.CRITICAL
                    "WARNING" -> AlertSeverity.WARNING
                    else -> AlertSeverity.INFO
                },
                hazardType = when (topHazard.hazardType.uppercase()) {
                    "ELECTRICAL" -> HazardType.ELECTRICAL
                    "HEAT" -> HazardType.HIGH_TEMPERATURE
                    "SHARP" -> HazardType.SHARP_SURFACE
                    "CHEMICAL" -> HazardType.CHEMICAL_SPILL
                    else -> HazardType.PHYSICAL_OBSTACLE
                },
                title = "Hazard Detected: ${topHazard.hazardType}",
                description = topHazard.description,
                recommendedAction = topHazard.recommendedSafeAction,
                overrideAllowed = topHazard.overridePermitted
            )
            _uiState.update {
                it.copy(
                    missionState = MissionState.HAZARD_BLOCKED,
                    activeSafetyAlert = alert,
                    isLoading = false
                )
            }
            return
        }

        _uiState.update {
            it.copy(
                missionState = MissionState.PLANNING,
                environmentalContext = EnvironmentalContext(
                    roomType = response.roomClassification,
                    ambientLux = response.ambientLux,
                    cameraStability = response.motionStability,
                    detectedObjects = response.detectedObjects.map { obj -> obj.label }
                ),
                isLoading = false
            )
        }
    }

    // 3. Connect to backend planning response (App shows plan)
    fun handleBackendPlan(response: BackendPlanResponse) {
        val steps = response.steps.map { dto ->
            PlanStep(
                stepNumber = dto.stepIndex,
                title = dto.title,
                physicalInstruction = dto.instruction,
                targetObject = dto.targetObjectName,
                toolNeeded = dto.toolRequired,
                safetyWarnings = dto.safetyWarnings,
                verificationCriterion = dto.expectedVerificationCriterion
            )
        }

        _uiState.update {
            it.copy(
                currentMissionId = response.missionId,
                planSteps = steps,
                missingPrerequisites = response.missingPrerequisites,
                detectedTools = response.detectedPrerequisites,
                missionState = MissionState.AWAITING_CONFIRMATION,
                activeStepIndex = 0,
                isLoading = false
            )
        }
    }

    // 4. User confirms plan
    fun confirmPlanAndStart() {
        _uiState.update {
            it.copy(
                missionState = MissionState.EXECUTING
            )
        }
    }

    // Trigger physical verification
    fun requestStepVerification() {
        _uiState.update {
            it.copy(
                missionState = MissionState.VERIFYING,
                isLoading = true
            )
        }
    }

    // 5. Connect to backend verification response (App verifies result)
    fun handleBackendVerification(response: BackendVerificationResponse) {
        val outcomeState = when {
            response.isVerified && response.confidenceScore >= 0.85f -> MissionState.COMPLETED
            response.verificationOutcome == "UNCERTAIN_REVIEW" || response.confidenceScore in 0.50f..0.84f -> MissionState.UNCERTAIN_REVIEW
            response.verificationOutcome == "HAZARD_BLOCKED" -> MissionState.HAZARD_BLOCKED
            else -> MissionState.VERIFYING // Stays uncompleted, awaiting retry
        }

        val result = VerificationResult(
            isVerified = response.isVerified && response.confidenceScore >= 0.85f,
            confidenceScore = response.confidenceScore,
            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
            reasoning = response.reasoningExplanation,
            detectedChanges = response.detectedPhysicalChanges,
            uncertaintyFactors = response.uncertaintyFactors
        )

        _uiState.update {
            it.copy(
                missionState = outcomeState,
                latestVerificationResult = result,
                isLoading = false
            )
        }
    }

    // Advance to next step once verified
    fun advanceToNextStep() {
        val nextIndex = _uiState.value.activeStepIndex + 1
        val totalSteps = _uiState.value.planSteps.size

        if (nextIndex < totalSteps) {
            _uiState.update {
                it.copy(
                    activeStepIndex = nextIndex,
                    missionState = MissionState.EXECUTING,
                    latestVerificationResult = null
                )
            }
        } else {
            // Whole mission finished
            _uiState.update {
                it.copy(
                    missionState = MissionState.COMPLETED,
                    latestVerificationResult = null
                )
            }
        }
    }

    // Safety abort action
    fun abortMission() {
        _uiState.update {
            MissionUiState()
        }
    }

    // Dismiss safety hazard with manual user confirmation
    fun dismissHazardOverride() {
        _uiState.update {
            it.copy(
                activeSafetyAlert = null,
                missionState = if (it.planSteps.isNotEmpty()) MissionState.AWAITING_CONFIRMATION else MissionState.IDLE
            )
        }
    }
}

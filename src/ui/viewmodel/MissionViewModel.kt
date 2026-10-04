package com.mirror.ui.viewmodel

import com.mirror.ui.model.*
import com.mirror.ui.network.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

enum class VerificationSimulationMode {
    NORMAL,            // High confidence >= 85%, verified complete
    UNCERTAIN_BLUR,    // Confidence 74%, motion blur requires human confirmation
    FALSE_SUCCESS_TEST,// Model claims done, but zero visual delta -> blocked
    HAZARD_DETECTED    // Physical danger in post frame -> blocked
}

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
    val isMissionCompleted: Boolean = false,
    val errorMessage: String? = null
)

/**
 * ViewModel connecting UI screen states to dynamic physical task decomposition,
 * real-time sensing telemetry, and strict multi-modal verification rules.
 */
class MissionViewModel {
    private val _uiState = MutableStateFlow(MissionUiState())
    val uiState: StateFlow<MissionUiState> = _uiState.asStateFlow()

    // 1. User enters task goal
    fun submitGoal(rawGoal: String) {
        val cleaned = rawGoal.trim()
        if (cleaned.isBlank() || cleaned.length < 3) {
            _uiState.update { it.copy(errorMessage = "Please enter an actionable physical goal.") }
            return
        }

        _uiState.update {
            it.copy(
                goalText = cleaned,
                missionState = MissionState.PERCEIVING,
                isLoading = false,
                errorMessage = null
            )
        }
    }

    // 2. Camera Viewfinder captures scene & decomposes intent
    fun captureSceneAndPlan() {
        val goal = _uiState.value.goalText.lowercase()
        val generatedSteps = generateDynamicPlanForGoal(goal)
        val env = generateEnvironmentalContext(goal)
        val missing = if (goal.contains("drill") || goal.contains("screw")) listOf("Phillips #2 Screwdriver") else emptyList()
        val detected = if (goal.contains("cable") || goal.contains("wire")) listOf("Zip-Ties (x4)", "Velcro Straps") else listOf("Safety Gloves", "Level Gauge")

        _uiState.update {
            it.copy(
                currentMissionId = "MIS-${System.currentTimeMillis() % 10000}",
                missionState = MissionState.PLANNING,
                planSteps = generatedSteps,
                missingPrerequisites = missing,
                detectedTools = detected,
                environmentalContext = env,
                activeStepIndex = 0,
                isLoading = false
            )
        }
    }

    // 3. User navigates from Mission Summary to Action Plan
    fun proceedToActionPlan() {
        _uiState.update {
            it.copy(
                missionState = MissionState.AWAITING_CONFIRMATION
            )
        }
    }

    // 4. User confirms action plan -> begins execution of active step
    fun confirmPlanAndExecute() {
        _uiState.update {
            it.copy(
                missionState = MissionState.EXECUTING
            )
        }
    }

    // 5. Request physical verification of active step
    fun verifyCurrentStep(mode: VerificationSimulationMode = VerificationSimulationMode.NORMAL) {
        val currentStep = _uiState.value.planSteps.getOrNull(_uiState.value.activeStepIndex)
            ?: return

        when (mode) {
            VerificationSimulationMode.NORMAL -> {
                val result = VerificationResult(
                    isVerified = true,
                    confidenceScore = 0.94f,
                    evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                    reasoning = "Post-action frame matches target physical criterion: ${currentStep.verificationCriterion}",
                    detectedChanges = listOf(
                        "Target object state physically altered",
                        "Keypoint displacement: 12.4cm alignment delta verified",
                        "No residual clutter detected in bounding region"
                    ),
                    uncertaintyFactors = emptyList()
                )
                _uiState.update {
                    it.copy(
                        missionState = MissionState.COMPLETED,
                        latestVerificationResult = result
                    )
                }
            }

            VerificationSimulationMode.UNCERTAIN_BLUR -> {
                val result = VerificationResult(
                    isVerified = false,
                    confidenceScore = 0.72f,
                    evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                    reasoning = "Perception confidence is 72% (below 85% safety threshold). Motion blur or specular reflection detected.",
                    detectedChanges = listOf("Partial object displacement detected"),
                    uncertaintyFactors = listOf("Camera stability: 0.54 (hand tremor)", "Shadow occludes target edge")
                )
                _uiState.update {
                    it.copy(
                        missionState = MissionState.UNCERTAIN_REVIEW,
                        latestVerificationResult = result
                    )
                }
            }

            VerificationSimulationMode.FALSE_SUCCESS_TEST -> {
                val result = VerificationResult(
                    isVerified = false,
                    confidenceScore = 0.12f,
                    evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
                    reasoning = "False success intercepted: Verbal completion assertion contradicts sensor frame delta (0.01 delta measured).",
                    detectedChanges = emptyList(),
                    uncertaintyFactors = listOf("Optical difference is zero; physical scene unchanged")
                )
                _uiState.update {
                    it.copy(
                        missionState = MissionState.VERIFYING,
                        latestVerificationResult = result
                    )
                }
            }

            VerificationSimulationMode.HAZARD_DETECTED -> {
                val alert = SafetyAlert(
                    id = "HAZ-INT-${System.currentTimeMillis() % 1000}",
                    severity = AlertSeverity.CRITICAL,
                    hazardType = HazardType.ELECTRICAL,
                    title = "High-Voltage Exposure Detected",
                    description = "Camera frame identified uninsulated 230V conductor adjacent to manipulation zone.",
                    recommendedAction = "Do NOT touch conductor. Cut circuit breaker before touching cables.",
                    overrideAllowed = true
                )
                _uiState.update {
                    it.copy(
                        missionState = MissionState.HAZARD_BLOCKED,
                        activeSafetyAlert = alert
                    )
                }
            }
        }
    }

    // 6. User accepts verification and advances to next step
    fun acceptVerificationAndAdvance() {
        val steps = _uiState.value.planSteps.toMutableList()
        val currentIndex = _uiState.value.activeStepIndex

        if (currentIndex in steps.indices) {
            steps[currentIndex] = steps[currentIndex].copy(isCompleted = true)
        }

        val nextIndex = currentIndex + 1
        if (nextIndex < steps.size) {
            _uiState.update {
                it.copy(
                    planSteps = steps,
                    activeStepIndex = nextIndex,
                    missionState = MissionState.EXECUTING,
                    latestVerificationResult = null
                )
            }
        } else {
            // All steps verified!
            _uiState.update {
                it.copy(
                    planSteps = steps,
                    missionState = MissionState.COMPLETED,
                    isMissionCompleted = true,
                    latestVerificationResult = null
                )
            }
        }
    }

    // Retake camera verification frame
    fun retakeVerification() {
        _uiState.update {
            it.copy(
                missionState = MissionState.PERCEIVING,
                latestVerificationResult = null
            )
        }
    }

    // Manual human confirmation override for uncertain states
    fun humanConfirmUncertainState() {
        val steps = _uiState.value.planSteps.toMutableList()
        val currentIndex = _uiState.value.activeStepIndex

        if (currentIndex in steps.indices) {
            steps[currentIndex] = steps[currentIndex].copy(isCompleted = true)
        }

        val nextIndex = currentIndex + 1
        if (nextIndex < steps.size) {
            _uiState.update {
                it.copy(
                    planSteps = steps,
                    activeStepIndex = nextIndex,
                    missionState = MissionState.EXECUTING,
                    latestVerificationResult = null
                )
            }
        } else {
            _uiState.update {
                it.copy(
                    planSteps = steps,
                    missionState = MissionState.COMPLETED,
                    isMissionCompleted = true,
                    latestVerificationResult = null
                )
            }
        }
    }

    // Safety alert triggers
    fun triggerSafetyAlert(hazardType: HazardType, title: String, description: String, safeAction: String) {
        val alert = SafetyAlert(
            id = "HAZ-${System.currentTimeMillis() % 1000}",
            severity = AlertSeverity.CRITICAL,
            hazardType = hazardType,
            title = title,
            description = description,
            recommendedAction = safeAction,
            overrideAllowed = true
        )
        _uiState.update {
            it.copy(
                missionState = MissionState.HAZARD_BLOCKED,
                activeSafetyAlert = alert
            )
        }
    }

    // Dismiss hazard with manual affirmation
    fun dismissHazardOverride() {
        _uiState.update {
            it.copy(
                activeSafetyAlert = null,
                missionState = if (it.planSteps.isNotEmpty()) MissionState.AWAITING_CONFIRMATION else MissionState.IDLE
            )
        }
    }

    // Safe abort mission
    fun abortMission() {
        _uiState.update {
            MissionUiState()
        }
    }

    // Return to home screen to start a new mission
    fun resetToHome() {
        _uiState.update {
            MissionUiState()
        }
    }

    // Select specific step in action plan
    fun selectStep(index: Int) {
        if (index in _uiState.value.planSteps.indices) {
            _uiState.update { it.copy(activeStepIndex = index) }
        }
    }

    // Dynamic decomposition generator
    private fun generateDynamicPlanForGoal(goal: String): List<PlanStep> {
        return when {
            goal.contains("cable") || goal.contains("wire") || goal.contains("socket") -> listOf(
                PlanStep(
                    stepNumber = 1,
                    title = "Isolate Power Source",
                    physicalInstruction = "Switch off power strip at the wall outlet before touching high-voltage cables.",
                    targetObject = "Wall AC Switch",
                    safetyWarnings = listOf("Shock hazard: Verify power LED is unlit"),
                    isCompleted = false,
                    verificationCriterion = "Power strip LED visually off; zero voltage reading"
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
                    title = "Fasten and Tension Fastener",
                    physicalInstruction = "Loop zip-tie around the bundled cables and pull firmly until tension holds them stationary.",
                    targetObject = "Zip-Tie Head",
                    toolNeeded = "Zip-Tie",
                    isCompleted = false,
                    verificationCriterion = "Zip-tie locked; bundle cannot slide freely"
                )
            )

            goal.contains("shelf") || goal.contains("assemble") || goal.contains("chair") || goal.contains("table") -> listOf(
                PlanStep(
                    stepNumber = 1,
                    title = "Inventory Hardware & Align Brackets",
                    physicalInstruction = "Lay out all corner brackets and M4 hex screws on the assembly surface.",
                    targetObject = "Hardware Fastener Tray",
                    toolNeeded = "Hex Key / Allen Wrench",
                    isCompleted = false,
                    verificationCriterion = "All 4 brackets aligned to pre-drilled pilot holes"
                ),
                PlanStep(
                    stepNumber = 2,
                    title = "Hand-Thread Primary Fasteners",
                    physicalInstruction = "Finger-tighten diagonal bolts 3 turns into corner joints without overtightening.",
                    targetObject = "Diagonal Joints A & B",
                    toolNeeded = "Hands",
                    isCompleted = false,
                    verificationCriterion = "Fasteners threaded 3-5mm without cross-threading"
                ),
                PlanStep(
                    stepNumber = 3,
                    title = "Torque to Flush Alignment",
                    physicalInstruction = "Tighten clockwise with hex key until bolt head seats flush with metal plate.",
                    targetObject = "Corner Fasteners",
                    toolNeeded = "Hex Key",
                    isCompleted = false,
                    verificationCriterion = "Bolt head flush; zero gap under washer"
                )
            )

            goal.contains("clean") || goal.contains("clear") || goal.contains("chemical") || goal.contains("bottle") -> listOf(
                PlanStep(
                    stepNumber = 1,
                    title = "Verify Container Seals",
                    physicalInstruction = "Check screw caps on solvent bottles before lifting. Wear nitrile gloves.",
                    targetObject = "Solvent Bottles",
                    safetyWarnings = listOf("Vapor hazard: Ensure room ventilation is active"),
                    isCompleted = false,
                    verificationCriterion = "All caps tightened; no wet rings on surface"
                ),
                PlanStep(
                    stepNumber = 2,
                    title = "Relocate to Dedicated Storage",
                    physicalInstruction = "Transfer bottles one by one into the yellow ventilated safety cabinet.",
                    targetObject = "Ventilated Cabinet Shelf",
                    toolNeeded = "Chemical Storage Tray",
                    isCompleted = false,
                    verificationCriterion = "Work table surface completely clear of bottles"
                ),
                PlanStep(
                    stepNumber = 3,
                    title = "Wipe & Inspect Surface",
                    physicalInstruction = "Wipe workbench down with neutralizing cleaner cloth.",
                    targetObject = "Workbench Surface",
                    toolNeeded = "Microfiber Cloth",
                    isCompleted = false,
                    verificationCriterion = "Optical reflectivity uniform; zero spill residue"
                )
            )

            else -> listOf(
                PlanStep(
                    stepNumber = 1,
                    title = "Perceive & Clear Work Envelope",
                    physicalInstruction = "Clear all foreign objects within a 30cm radius around the target area.",
                    targetObject = "Target Workspace",
                    isCompleted = false,
                    verificationCriterion = "30cm envelope clear of obstructions"
                ),
                PlanStep(
                    stepNumber = 2,
                    title = "Align Component into Position",
                    physicalInstruction = "Position the component according to visible orientation markers.",
                    targetObject = "Target Component",
                    toolNeeded = "Hands",
                    isCompleted = false,
                    verificationCriterion = "Component oriented to reference markers"
                ),
                PlanStep(
                    stepNumber = 3,
                    title = "Verify Mechanical Stability",
                    physicalInstruction = "Apply gentle 5N lateral pressure to confirm solid engagement.",
                    targetObject = "Assembled Joint",
                    isCompleted = false,
                    verificationCriterion = "Zero mechanical play; structure holds position"
                )
            )
        }
    }

    private fun generateEnvironmentalContext(goal: String): EnvironmentalContext {
        return EnvironmentalContext(
            roomType = if (goal.contains("desk") || goal.contains("cable")) "Home Office / Desk" else if (goal.contains("shelf") || goal.contains("assemble")) "Living Room / Assembly Area" else "Workshop Room",
            ambientLux = 380f,
            ambientNoiseDb = 42f,
            detectedObjects = listOf("Desk Surface", "Power Adapter", "Cable Bundle", "Zip-Ties"),
            missingPrerequisites = emptyList(),
            cameraStability = 0.98f
        )
    }
}

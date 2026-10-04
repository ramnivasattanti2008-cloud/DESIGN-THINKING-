package com.mirror.ui.model

/**
 * Represents the primary user goal given via voice or text input.
 */
data class TaskGoal(
    val id: String,
    val rawPrompt: String,
    val source: GoalSource = GoalSource.VOICE,
    val timestamp: Long = System.currentTimeMillis(),
    val urgency: UrgencyLevel = UrgencyLevel.NORMAL
)

enum class GoalSource {
    VOICE,
    TEXT,
    CAMERA_SUGGESTION
}

enum class UrgencyLevel {
    LOW,
    NORMAL,
    HIGH,
    EMERGENCY
}

/**
 * State machine stages of a MIRROR task lifecycle.
 */
enum class MissionState {
    IDLE,                      // Awaiting user goal
    PERCEIVING,                // Camera and sensors scanning environment
    PLANNING,                  // Formulating decomposed action plan
    AWAITING_CONFIRMATION,     // Plan presented, waiting for user approval
    EXECUTING,                 // Action in progress by user or automated step
    VERIFYING,                 // Actively confirming physical post-conditions
    COMPLETED,                 // Strictly verified outcome confirmed
    UNCERTAIN_REVIEW,          // Verification ambiguous, human inspection required
    HAZARD_BLOCKED             // Safety constraint violated, execution halted
}

/**
 * Discrete, verifiable physical step in an action plan.
 */
data class PlanStep(
    val stepNumber: Int,
    val title: String,
    val physicalInstruction: String,
    val targetObject: String,
    val toolNeeded: String? = null,
    val safetyWarnings: List<String> = emptyList(),
    val isConfirmed: Boolean = false,
    val isCompleted: Boolean = false,
    val verificationCriterion: String
)

/**
 * High-priority physical hazard alert.
 */
data class SafetyAlert(
    val id: String,
    val severity: AlertSeverity,
    val hazardType: HazardType,
    val title: String,
    val description: String,
    val recommendedAction: String,
    val overrideAllowed: Boolean = false
)

enum class AlertSeverity {
    INFO,
    WARNING,
    CRITICAL
}

enum class HazardType {
    ELECTRICAL,
    HIGH_TEMPERATURE,
    SHARP_SURFACE,
    CHEMICAL_SPILL,
    PHYSICAL_OBSTACLE,
    PINCH_POINT
}

/**
 * Evidence and outcome of physical post-condition verification.
 */
data class VerificationResult(
    val isVerified: Boolean,
    val confidenceScore: Float, // 0.0f to 1.0f
    val evidenceType: EvidenceType,
    val reasoning: String,
    val detectedChanges: List<String>,
    val uncertaintyFactors: List<String> = emptyList(),
    val status: String = if (isVerified) "verified" else "not_verified"
)

enum class EvidenceType {
    VISUAL_CAMERA_DIFF,
    AUDIO_ACOUSTIC_SIGNATURE,
    INERTIAL_SENSOR,
    USER_AFFIRMATION
}

/**
 * Real-time environmental sensing data.
 */
data class EnvironmentalContext(
    val roomType: String = "Unspecified Room",
    val ambientLux: Float = 350f,
    val ambientNoiseDb: Float = 42f,
    val detectedObjects: List<String> = emptyList(),
    val missingPrerequisites: List<String> = emptyList(),
    val cameraStability: Float = 0.95f
)

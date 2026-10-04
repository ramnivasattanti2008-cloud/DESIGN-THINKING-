package com.mirror.ui.network

import com.mirror.ui.model.*

/**
 * UI-side network response DTOs mapping backend REST / WebSocket responses
 * directly to Compose screen states.
 */

data class BackendPerceptionResponse(
    val frameId: String,
    val timestampMs: Long,
    val ambientLux: Float,
    val motionStability: Float,
    val detectedObjects: List<DetectedObjectDto>,
    val detectedHazards: List<HazardDto>,
    val roomClassification: String
)

data class DetectedObjectDto(
    val label: String,
    val confidence: Float,
    val boundingBox: BoundingBoxDto,
    val isTargetTool: Boolean = false
)

data class BoundingBoxDto(
    val xMin: Float, // Normalized 0.0 to 1.0
    val yMin: Float,
    val xMax: Float,
    val yMax: Float
)

data class HazardDto(
    val hazardType: String,
    val severity: String,
    val description: String,
    val recommendedSafeAction: String,
    val overridePermitted: Boolean
)

data class BackendPlanResponse(
    val missionId: String,
    val interpretedIntent: String,
    val steps: List<PlanStepDto>,
    val detectedPrerequisites: List<String>,
    val missingPrerequisites: List<String>,
    val preliminarySafetyNotes: List<String>
)

data class PlanStepDto(
    val stepIndex: Int,
    val title: String,
    val instruction: String,
    val targetObjectName: String,
    val toolRequired: String?,
    val safetyWarnings: List<String>,
    val expectedVerificationCriterion: String
)

data class BackendVerificationResponse(
    val isVerified: Boolean,
    val confidenceScore: Float, // 0.0 to 1.0
    val verificationOutcome: String, // "COMPLETED", "UNCERTAIN_REVIEW", "FAILED", "HAZARD_BLOCKED"
    val visualDiffScore: Float,
    val detectedPhysicalChanges: List<String>,
    val uncertaintyFactors: List<String>,
    val reasoningExplanation: String,
    val isFalseSuccessIntercepted: Boolean = false
)

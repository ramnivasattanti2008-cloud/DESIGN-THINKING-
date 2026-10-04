package com.mirror.mobile.integration

import com.mirror.mobile.api.BackendGate
import com.mirror.mobile.api.BackendStep
import com.mirror.mobile.api.VerifyReply
import com.mirror.mobile.api.WorldInfo
import com.mirror.ui.network.BackendPerceptionResponse
import com.mirror.ui.network.BackendPlanResponse
import com.mirror.ui.network.BackendVerificationResponse
import com.mirror.ui.network.BoundingBoxDto
import com.mirror.ui.network.DetectedObjectDto
import com.mirror.ui.network.HazardDto
import com.mirror.ui.network.PlanStepDto

/**
 * Maps backend replies onto the UI seat's DTOs (src/ui/network). The one rule that matters:
 * a step is verified only when the backend says `verified` AND confidence clears the bar.
 * Unknown statuses count as NOT verified.
 */
object BackendAdapter {

    /** Same bar the UI view model applies (MissionViewModel.handleBackendVerification). */
    const val CONFIDENCE_BAR = 0.85f

    fun isStepVerified(r: VerifyReply): Boolean = r.status == "verified" && r.confidence >= CONFIDENCE_BAR

    fun verification(r: VerifyReply): BackendVerificationResponse {
        val outcome = when (r.status) {
            "verified" -> if (r.confidence >= CONFIDENCE_BAR) "COMPLETED" else "UNCERTAIN_REVIEW"
            "not_verified" -> "FAILED"
            else -> "UNCERTAIN_REVIEW" // cannot_tell and anything unknown
        }
        val uncertainty = buildList {
            addAll(r.evidenceMissing)
            if (r.framePoor) add("Photo too blurry or dark")
            if (r.status == "verified" && r.confidence < CONFIDENCE_BAR) add("Confidence below the required level")
        }
        return BackendVerificationResponse(
            isVerified = isStepVerified(r),
            confidenceScore = r.confidence,
            verificationOutcome = outcome,
            visualDiffScore = 0f, // the backend does not compute one; do not invent it
            detectedPhysicalChanges = r.evidenceSeen,
            uncertaintyFactors = uncertainty,
            reasoningExplanation = r.reason,
            isFalseSuccessIntercepted = r.status == "verified" && r.confidence < CONFIDENCE_BAR
        )
    }

    fun plan(sessionId: String, intent: String, step: BackendStep, gate: BackendGate?): BackendPlanResponse {
        val warnings = buildList {
            if (gate?.decision == "confirm") add("This step needs your explicit OK before you start.")
            if (step.tier == "A0") add("Safety first: no other action until this is resolved.")
        }
        return BackendPlanResponse(
            missionId = sessionId,
            interpretedIntent = intent,
            steps = listOf(
                PlanStepDto(
                    stepIndex = 0,
                    title = step.instruction.removeSuffix("."),
                    instruction = step.instruction,
                    targetObjectName = targetOf(step),
                    toolRequired = null,
                    safetyWarnings = warnings,
                    expectedVerificationCriterion = step.expectedEvidence.joinToString("; ")
                )
            ),
            detectedPrerequisites = emptyList(),
            missingPrerequisites = emptyList(),
            preliminarySafetyNotes = warnings
        )
    }

    /** The backend does not return boxes, lux or stability, so none are reported. */
    fun perception(frameId: String, world: WorldInfo, intent: String): BackendPerceptionResponse =
        BackendPerceptionResponse(
            frameId = frameId,
            timestampMs = System.currentTimeMillis(),
            ambientLux = 0f,
            motionStability = 0f,
            detectedObjects = world.labels.map { DetectedObjectDto(it, 0f, BoundingBoxDto(0f, 0f, 0f, 0f)) },
            detectedHazards = emptyList(),
            roomClassification = intent
        )

    /** Used for refusals (goal or step blocked by policy) and for hazards seen in the scene. */
    fun hazard(type: String, description: String, safeAction: String): BackendPerceptionResponse =
        BackendPerceptionResponse(
            frameId = "blocked",
            timestampMs = System.currentTimeMillis(),
            ambientLux = 0f,
            motionStability = 0f,
            detectedObjects = emptyList(),
            detectedHazards = listOf(HazardDto(type, "CRITICAL", description, safeAction, overridePermitted = false)),
            roomClassification = ""
        )

    private fun targetOf(step: BackendStep): String =
        step.expectedEvidence.firstOrNull()?.removePrefix("no ")?.removeSuffix(" visible") ?: "the area"
}

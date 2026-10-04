package com.mirror.mobile.integration

import com.mirror.mobile.api.BackendGate
import com.mirror.mobile.api.BackendStep
import com.mirror.mobile.api.VerifyReply
import com.mirror.ui.model.AlertSeverity
import com.mirror.ui.model.EvidenceType
import com.mirror.ui.model.HazardType
import com.mirror.ui.model.PlanStep
import com.mirror.ui.model.SafetyAlert
import com.mirror.ui.model.VerificationResult

/**
 * Maps backend replies onto the UI seat's presentational models (src/ui/model), which the
 * screens render. The one rule that matters: a step is verified only when the backend says
 * `verified` AND confidence clears the bar. Unknown statuses count as NOT verified.
 */
object BackendAdapter {

    /** Minimum confidence for a step to count as verified. A heuristic bar, not a calibrated one. */
    const val CONFIDENCE_BAR = 0.85f

    fun isStepVerified(r: VerifyReply): Boolean = r.status == "verified" && r.confidence >= CONFIDENCE_BAR

    fun verificationResult(r: VerifyReply): VerificationResult {
        val uncertainty = buildList {
            addAll(r.evidenceMissing)
            if (r.framePoor) add("Photo too blurry or dark")
            if (r.status == "verified" && r.confidence < CONFIDENCE_BAR) add("Confidence below the required level")
            if (r.status !in KNOWN_STATUSES) add("Unrecognised server status")
        }
        return VerificationResult(
            isVerified = isStepVerified(r),
            confidenceScore = r.confidence,
            evidenceType = EvidenceType.VISUAL_CAMERA_DIFF,
            reasoning = r.reason,
            detectedChanges = r.evidenceSeen,
            uncertaintyFactors = uncertainty
        )
    }

    fun planStep(stepNumber: Int, step: BackendStep, gate: BackendGate?): PlanStep {
        val warnings = buildList {
            if (gate?.decision == "confirm") add("This step needs your explicit OK before you start.")
            if (step.tier == "A0") add("Safety first: no other action until this is resolved.")
        }
        return PlanStep(
            stepNumber = stepNumber,
            title = step.instruction.removeSuffix("."),
            physicalInstruction = step.instruction,
            targetObject = targetOf(step),
            toolNeeded = null,
            safetyWarnings = warnings,
            verificationCriterion = step.expectedEvidence.joinToString("; ")
        )
    }

    /** Refusal for a goal or step blocked by policy. No override is offered. */
    fun refusal(id: String, message: String): SafetyAlert = SafetyAlert(
        id = id,
        severity = AlertSeverity.CRITICAL,
        hazardType = HazardType.PHYSICAL_OBSTACLE,
        title = "MIRROR will not guide this",
        description = message,
        recommendedAction = "Ask a qualified professional or emergency services.",
        overrideAllowed = false
    )

    /** A hazard seen in the scene. The flow stops until the area is made safe and scanned again. */
    fun hazard(id: String, hazards: List<String>): SafetyAlert = SafetyAlert(
        id = id,
        severity = AlertSeverity.CRITICAL,
        hazardType = hazardType(hazards.firstOrNull().orEmpty()),
        title = "Hazard detected",
        description = "A hazard is visible: ${hazards.joinToString(", ")}.",
        recommendedAction = "Make the area safe or leave it, then scan again.",
        overrideAllowed = false
    )

    private fun hazardType(label: String): HazardType = when {
        label.contains("smoke") || label.contains("fire") -> HazardType.HIGH_TEMPERATURE
        label.contains("wiring") || label.contains("socket") -> HazardType.ELECTRICAL
        label.contains("sharp") -> HazardType.SHARP_SURFACE
        else -> HazardType.PHYSICAL_OBSTACLE
    }

    private fun targetOf(step: BackendStep): String =
        step.expectedEvidence.firstOrNull()?.removePrefix("no ")?.removeSuffix(" visible") ?: "the area"

    private val KNOWN_STATUSES = setOf("verified", "not_verified", "cannot_tell")
}

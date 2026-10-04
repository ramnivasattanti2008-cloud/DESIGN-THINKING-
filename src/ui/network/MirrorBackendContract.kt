package com.mirror.ui.network

/**
 * Exact Kotlin data contract matching the MIRROR FastAPI /v1 endpoints and contracts/*.schema.json.
 * 
 * Response rules the frontend relies on:
 * 1. plan.outcome == "completed" is the ONLY success claim, and only after verified evidence.
 * 2. plan.outcome == "no_action_needed" is NOT success; nothing to do with 0 verified steps.
 * 3. verify.status == "cannot_tell" represents an uncertain state (poor frame, ungrounded anchor).
 * 4. goal_gate.decision == "block" (Tier A3) immediately refuses the session with safety message.
 * 5. gate.decision == "confirm" (Tier A2) mandates explicit user confirmation before action.
 */

data class CreateSessionRequest(
    val goal: String
)

data class GateDecisionDto(
    val step_id: String,
    val tier: String,      // "A0", "A1", "A2", "A3"
    val decision: String,  // "allow", "confirm", "block"
    val rule_id: String
)

data class CreateSessionResponse(
    val session_id: String,
    val interpreted_intent: String,
    val goal_gate: GateDecisionDto,
    val blocked: Boolean,
    val message: String?
)

data class FrameDto(
    val id: String,
    val blur: Float = 0.0f,
    val brightness: Float = 0.5f,
    val data_b64: String? = null,
    val media_type: String = "image/jpeg",
    val fake_labels: List<String> = emptyList()
)

data class ObserveRequest(
    val frames: List<FrameDto>
)

data class ObservationDto(
    val id: String,
    val label: String,
    val confidence: Float,
    val where_hint: String = "",
    val source_frame: String
)

data class WorldStateDto(
    val session_id: String,
    val observations: List<ObservationDto> = emptyList(),
    val unknowns: List<String> = emptyList(),
    val hazards: List<String> = emptyList()
)

data class StepDto(
    val id: String,
    val instruction: String,
    val tier: String,      // "A0", "A1", "A2", "A3"
    val tier_reason: String = "",
    val expected_evidence: List<String> = emptyList(),
    val rollback_hint: String? = null
)

data class PlanResponse(
    val outcome: String,   // "step", "completed", "no_action_needed", "needs_observation", "blocked_goal", "needs_human"
    val done: Boolean,
    val step: StepDto?,
    val gate: GateDecisionDto?,
    val message: String?
)

data class VerifyRequest(
    val frames: List<FrameDto>
)

data class VerifyResultDto(
    val step_id: String,
    val status: String,    // "verified", "not_verified", "cannot_tell"
    val evidence_seen: List<String> = emptyList(),
    val evidence_missing: List<String> = emptyList(),
    val frame_quality: String = "ok", // "ok", "poor"
    val confidence: Float = 0.0f,
    val reason: String = ""
)

data class SessionDetailDto(
    val goal: String,
    val world: WorldStateDto,
    val current: StepDto?,
    val log: List<Map<String, Any?>> = emptyList(),
    val verified_steps: Int = 0
)

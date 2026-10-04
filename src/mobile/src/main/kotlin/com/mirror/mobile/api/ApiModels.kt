package com.mirror.mobile.api

/**
 * App-side view of the backend `/v1` API. Mirrors contracts/*.schema.json and src/api/main.py.
 * Change the contract first, then this file.
 */

data class FrameUpload(
    val id: String,
    val blur: Float,          // 0 sharp .. 1 unusable, computed on device
    val brightness: Float,    // 0 dark .. 1 bright, computed on device
    val jpegBase64: String
)

data class SessionInfo(
    val sessionId: String,
    val interpretedIntent: String,
    val blocked: Boolean,
    val message: String?
)

data class WorldInfo(
    val labels: List<String>,
    val hazards: List<String>,
    val unknowns: List<String>
)

data class BackendStep(
    val id: String,
    val instruction: String,
    val tier: String,
    val tierReason: String,
    val expectedEvidence: List<String>
)

data class BackendGate(
    val tier: String,
    val decision: String,   // allow | confirm | block
    val ruleId: String
)

/** outcome: step | completed | no_action_needed | needs_observation | blocked_goal | needs_human */
data class PlanReply(
    val outcome: String,
    val step: BackendStep?,
    val gate: BackendGate?,
    val message: String?
)

/** status: verified | not_verified | cannot_tell. Anything else must be treated as not verified. */
data class VerifyReply(
    val stepId: String,
    val status: String,
    val evidenceSeen: List<String>,
    val evidenceMissing: List<String>,
    val framePoor: Boolean,
    val confidence: Float,
    val reason: String
)

/** Raised when the backend cannot be reached or replies with an error. Never means success. */
class ApiException(val httpCode: Int?, message: String) : Exception(message)

/** Raised when a camera frame cannot be captured. Never means success. */
class CaptureException(message: String) : Exception(message)

interface Backend {
    suspend fun createSession(goal: String): SessionInfo
    suspend fun observe(sessionId: String, frames: List<FrameUpload>): WorldInfo
    suspend fun plan(sessionId: String): PlanReply
    suspend fun verify(sessionId: String, frames: List<FrameUpload>): VerifyReply
}

interface FrameSource {
    suspend fun capture(id: String): FrameUpload
}

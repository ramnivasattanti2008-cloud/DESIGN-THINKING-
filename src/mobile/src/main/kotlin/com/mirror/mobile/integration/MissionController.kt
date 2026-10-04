package com.mirror.mobile.integration

import com.mirror.mobile.api.ApiException
import com.mirror.mobile.api.Backend
import com.mirror.mobile.api.CaptureException
import com.mirror.mobile.api.FrameSource
import com.mirror.mobile.api.PlanReply
import com.mirror.mobile.api.WorldInfo
import com.mirror.ui.model.PlanStep
import com.mirror.ui.model.SafetyAlert
import com.mirror.ui.model.VerificationResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

enum class AppScreen { HOME, CAMERA, SUMMARY, PLAN, EXECUTING, VERIFICATION, COMPLETED }

data class AppState(
    val screen: AppScreen = AppScreen.HOME,
    val busy: Boolean = false,
    /** User-facing message: errors, refusals, "nothing to do". Never a success claim. */
    val notice: String? = null,
    /** True only after the backend confirmed the current step with enough confidence. */
    val stepVerified: Boolean = false,
    val verifiedSteps: Int = 0
)

/** What the screens render. All of it comes from backend replies; none of it is sample data. */
data class MissionData(
    val goalText: String = "",
    val planSteps: List<PlanStep> = emptyList(),
    val activeStepIndex: Int = 0,
    val latestVerification: VerificationResult? = null,
    val activeAlert: SafetyAlert? = null
)

/**
 * Drives the loop: goal -> observe -> plan -> (user acts) -> verify -> next plan.
 * The COMPLETED screen is reachable only from a backend `completed` plan outcome, which the
 * backend gives only after at least one verified step and a fresh scan with nothing left to do.
 */
class MissionController(
    private val backend: Backend,
    private val frames: FrameSource
) {
    private val _app = MutableStateFlow(AppState())
    val app: StateFlow<AppState> = _app.asStateFlow()

    private val _data = MutableStateFlow(MissionData())
    val data: StateFlow<MissionData> = _data.asStateFlow()

    private var sessionId: String? = null
    private var frameCounter = 0
    private var alertCounter = 0
    private var stepCounter = 0

    suspend fun startGoal(goal: String) = guarded {
        if (goal.isBlank()) {
            notice("Please enter a goal first.")
            return@guarded
        }
        _data.value = MissionData(goalText = goal.trim())
        stepCounter = 0
        val s = backend.createSession(goal.trim())
        sessionId = s.sessionId
        if (s.blocked) {
            refuse(s.message ?: REFUSAL, AppScreen.HOME)
            return@guarded
        }
        _app.update { it.copy(screen = AppScreen.CAMERA, notice = null, stepVerified = false, verifiedSteps = 0) }
    }

    /** Camera screen "Capture": take a real frame, observe, then plan. */
    suspend fun captureScene() = guarded {
        val sid = requireSession()
        val frame = frames.capture("scene-${++frameCounter}")
        val world = backend.observe(sid, listOf(frame))
        if (world.hazards.isNotEmpty()) {
            showHazard(world)
            return@guarded
        }
        applyPlan(backend.plan(sid), firstStep = true)
    }

    fun retakeScan() = _app.update { it.copy(screen = AppScreen.CAMERA, notice = null) }

    fun proceedToPlan() = _app.update { it.copy(screen = AppScreen.PLAN, notice = null) }

    fun beginStep() = _app.update { it.copy(screen = AppScreen.EXECUTING, notice = null, stepVerified = false) }

    /** "I did it": take a fresh frame and ask the backend whether the step really worked. */
    suspend fun verifyStep() = guarded {
        val sid = requireSession()
        val frame = frames.capture("verify-${++frameCounter}")
        val reply = backend.verify(sid, listOf(frame))
        _data.update { it.copy(latestVerification = BackendAdapter.verificationResult(reply)) }
        val ok = BackendAdapter.isStepVerified(reply)
        _app.update {
            it.copy(
                screen = AppScreen.VERIFICATION,
                stepVerified = ok,
                notice = if (ok) null else reply.reason.ifBlank { "This step could not be verified." }
            )
        }
    }

    /** Only moves on if the current step was verified. Otherwise nothing changes except the notice. */
    suspend fun acceptVerification() = guarded {
        if (!_app.value.stepVerified) {
            notice("This step is not verified yet. Finish it and take another photo.")
            return@guarded
        }
        _app.update { it.copy(verifiedSteps = it.verifiedSteps + 1, stepVerified = false) }
        _data.update { it.copy(latestVerification = null) }
        applyPlan(backend.plan(requireSession()), firstStep = false)
    }

    fun retakeVerification() =
        _app.update { it.copy(screen = AppScreen.EXECUTING, notice = null, stepVerified = false) }

    /** Closes the alert only. The hazard or refusal is re-checked on the next scan, never skipped. */
    fun dismissAlert() {
        _data.update { it.copy(activeAlert = null) }
        _app.update { it.copy(notice = null) }
    }

    fun abort() {
        sessionId = null
        _data.value = MissionData()
        _app.value = AppState()
    }

    // ---- internals ----

    private fun applyPlan(reply: PlanReply, firstStep: Boolean) {
        when (reply.outcome) {
            "step" -> {
                val step = reply.step
                if (step == null || reply.gate?.decision == "block") {
                    refuse(reply.message ?: REFUSAL, _app.value.screen)
                    return
                }
                _data.update {
                    it.copy(
                        planSteps = listOf(BackendAdapter.planStep(++stepCounter, step, reply.gate)),
                        activeStepIndex = 0,
                        latestVerification = null
                    )
                }
                _app.update {
                    it.copy(screen = if (firstStep) AppScreen.SUMMARY else AppScreen.PLAN, notice = null, stepVerified = false)
                }
            }
            "completed" -> _app.update { it.copy(screen = AppScreen.COMPLETED, notice = null) }
            "no_action_needed" -> {
                sessionId = null
                _data.value = MissionData()
                _app.value = AppState(notice = "Nothing needed changing, so nothing was verified. No result to report.")
            }
            "needs_observation" ->
                _app.update { it.copy(screen = AppScreen.CAMERA, notice = reply.message ?: "No clear view yet. Scan again.") }
            "blocked_goal" -> refuse(reply.message ?: REFUSAL, AppScreen.HOME)
            "needs_human" ->
                _app.update { it.copy(screen = AppScreen.EXECUTING, notice = reply.message ?: "Please check the step yourself.") }
            else ->
                _app.update { it.copy(notice = "The server sent an answer this app does not understand. Nothing was marked done.") }
        }
    }

    private fun refuse(message: String, screen: AppScreen) {
        _data.update { it.copy(activeAlert = BackendAdapter.refusal("refusal-${++alertCounter}", message)) }
        _app.update { it.copy(screen = screen, notice = null, stepVerified = false) }
    }

    private fun showHazard(world: WorldInfo) {
        _data.update { it.copy(activeAlert = BackendAdapter.hazard("hazard-${++alertCounter}", world.hazards)) }
        _app.update { it.copy(screen = AppScreen.CAMERA, notice = null) }
    }

    private fun requireSession(): String = sessionId ?: throw ApiException(null, "No active session. Start again.")

    private fun notice(text: String) = _app.update { it.copy(notice = text) }

    private suspend fun guarded(block: suspend () -> Unit) {
        _app.update { it.copy(busy = true) }
        try {
            block()
        } catch (e: ApiException) {
            notice(e.message ?: "Server error.")
        } catch (e: CaptureException) {
            notice(e.message ?: "Camera error.")
        } finally {
            _app.update { it.copy(busy = false) }
        }
    }

    private companion object {
        const val REFUSAL = "MIRROR will not guide this. Ask a qualified professional or emergency services."
    }
}

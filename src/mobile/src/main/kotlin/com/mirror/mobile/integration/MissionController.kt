package com.mirror.mobile.integration

import com.mirror.mobile.api.ApiException
import com.mirror.mobile.api.Backend
import com.mirror.mobile.api.CaptureException
import com.mirror.mobile.api.FrameSource
import com.mirror.mobile.api.PlanReply
import com.mirror.mobile.api.WorldInfo
import com.mirror.ui.viewmodel.MissionViewModel
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

/**
 * Drives the loop: goal -> observe -> plan -> (user acts) -> verify -> next plan.
 * UI state for plans and verification lives in the UI seat's [MissionViewModel]; this class decides
 * which screen is next. The COMPLETED screen is reachable only from a backend `completed` plan
 * outcome, which the backend gives only after at least one verified step.
 */
class MissionController(
    private val backend: Backend,
    private val frames: FrameSource,
    val vm: MissionViewModel = MissionViewModel()
) {
    private val _app = MutableStateFlow(AppState())
    val app: StateFlow<AppState> = _app.asStateFlow()

    private var sessionId: String? = null
    private var intent: String = ""
    private var frameCounter = 0

    suspend fun startGoal(goal: String) = guarded {
        vm.submitGoal(goal)
        vm.uiState.value.errorMessage?.let { notice(it); return@guarded }
        val s = backend.createSession(goal.trim())
        sessionId = s.sessionId
        intent = s.interpretedIntent
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
        applyPlan(backend.plan(sid), world, frame.id, firstStep = true)
    }

    fun retakeScan() = _app.update { it.copy(screen = AppScreen.CAMERA, notice = null) }

    fun proceedToPlan() = _app.update { it.copy(screen = AppScreen.PLAN, notice = null) }

    fun beginStep() {
        vm.confirmPlanAndStart()
        _app.update { it.copy(screen = AppScreen.EXECUTING, notice = null, stepVerified = false) }
    }

    /** "I did it": take a fresh frame and ask the backend whether the step really worked. */
    suspend fun verifyStep() = guarded {
        val sid = requireSession()
        vm.requestStepVerification()
        val frame = frames.capture("verify-${++frameCounter}")
        val reply = backend.verify(sid, listOf(frame))
        vm.handleBackendVerification(BackendAdapter.verification(reply))
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
        applyPlan(backend.plan(requireSession()), null, null, firstStep = false)
    }

    fun retakeVerification() =
        _app.update { it.copy(screen = AppScreen.EXECUTING, notice = null, stepVerified = false) }

    fun dismissAlert() {
        vm.dismissHazardOverride() // closes the modal only; the hazard is re-checked on the next scan
        _app.update { it.copy(notice = null) }
    }

    fun abort() {
        vm.abortMission()
        sessionId = null
        _app.value = AppState()
    }

    // ---- internals ----

    private suspend fun applyPlan(reply: PlanReply, world: WorldInfo?, frameId: String?, firstStep: Boolean) {
        when (reply.outcome) {
            "step" -> {
                val step = reply.step
                if (step == null || reply.gate?.decision == "block") {
                    refuse(reply.message ?: REFUSAL, _app.value.screen)
                    return
                }
                if (world != null && frameId != null) {
                    vm.handleBackendPerception(BackendAdapter.perception(frameId, world, intent))
                }
                vm.handleBackendPlan(BackendAdapter.plan(requireSession(), intent, step, reply.gate))
                _app.update {
                    it.copy(screen = if (firstStep) AppScreen.SUMMARY else AppScreen.PLAN, notice = null, stepVerified = false)
                }
            }
            "completed" -> {
                vm.advanceToNextStep() // single-step plans: this is the whole mission, and the backend confirmed it
                _app.update { it.copy(screen = AppScreen.COMPLETED, notice = null) }
            }
            "no_action_needed" -> {
                vm.abortMission()
                _app.update {
                    AppState(notice = "Nothing needed changing, so nothing was verified. No result to report.")
                }
                sessionId = null
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
        vm.handleBackendPerception(
            BackendAdapter.hazard("POLICY", message, "Ask a qualified professional or emergency services.")
        )
        _app.update { it.copy(screen = screen, notice = null, stepVerified = false) }
    }

    private fun showHazard(world: WorldInfo) {
        vm.handleBackendPerception(
            BackendAdapter.hazard(
                "HAZARD",
                "A hazard is visible: ${world.hazards.joinToString(", ")}.",
                "Make the area safe or leave it, then scan again."
            )
        )
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

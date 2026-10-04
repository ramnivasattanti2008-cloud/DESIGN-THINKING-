package com.mirror.mobile

import com.mirror.mobile.api.ApiException
import com.mirror.mobile.api.Backend
import com.mirror.mobile.api.BackendGate
import com.mirror.mobile.api.BackendStep
import com.mirror.mobile.api.CaptureException
import com.mirror.mobile.api.FrameSource
import com.mirror.mobile.api.FrameUpload
import com.mirror.mobile.api.PlanReply
import com.mirror.mobile.api.SessionInfo
import com.mirror.mobile.api.VerifyReply
import com.mirror.mobile.api.WorldInfo
import com.mirror.mobile.integration.AppScreen
import com.mirror.mobile.integration.MissionController
import com.mirror.ui.model.MissionState
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Scripted backend: the controller logic is real, the server replies are canned. */
private class ScriptedBackend(
    var blocked: Boolean = false,
    var world: WorldInfo = WorldInfo(listOf("cup", "lamp"), emptyList(), emptyList()),
    val plans: ArrayDeque<PlanReply> = ArrayDeque(),
    var verify: VerifyReply? = null,
    var failWith: ApiException? = null
) : Backend {
    var verifyCalls = 0
    override suspend fun createSession(goal: String): SessionInfo {
        failWith?.let { throw it }
        return SessionInfo("sid", "tidy the space", blocked, if (blocked) "refused" else null)
    }
    override suspend fun observe(sessionId: String, frames: List<FrameUpload>): WorldInfo {
        failWith?.let { throw it }
        return world
    }
    override suspend fun plan(sessionId: String): PlanReply = plans.removeFirst()
    override suspend fun verify(sessionId: String, frames: List<FrameUpload>): VerifyReply {
        verifyCalls++
        failWith?.let { throw it }
        return verify!!
    }
}

private class FakeFrames(var fail: Boolean = false) : FrameSource {
    override suspend fun capture(id: String): FrameUpload {
        if (fail) throw CaptureException("no camera")
        return FrameUpload(id, 0f, 0.5f, "AAAA")
    }
}

private val step = BackendStep("s1", "Move the cup off the surface.", "A1", "tidy", listOf("no cup visible"))
private val stepReply = PlanReply("step", step, BackendGate("A1", "allow", "R-planner"), null)

private fun verified(conf: Float, status: String = "verified") =
    VerifyReply("s1", status, listOf("no cup visible"), emptyList(), false, conf, "reason")

class MissionControllerTest {

    private fun controller(b: ScriptedBackend, f: FakeFrames = FakeFrames()) = MissionController(b, f)

    @Test
    fun happyPathCompletesOnlyAfterVerifiedStepAndBackendCompleted() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(stepReply, PlanReply("completed", null, null, null))), verify = verified(0.9f))
        val c = controller(b)
        c.startGoal("tidy my desk")
        assertEquals(AppScreen.CAMERA, c.app.value.screen)
        c.captureScene()
        assertEquals(AppScreen.SUMMARY, c.app.value.screen)
        c.proceedToPlan(); c.beginStep()
        assertEquals(AppScreen.EXECUTING, c.app.value.screen)
        c.verifyStep()
        assertEquals(AppScreen.VERIFICATION, c.app.value.screen)
        assertTrue(c.app.value.stepVerified)
        c.acceptVerification()
        assertEquals(AppScreen.COMPLETED, c.app.value.screen)
        assertEquals(1, c.app.value.verifiedSteps)
    }

    @Test
    fun notVerifiedStepCannotBeAccepted() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(stepReply)), verify = verified(0.9f, "not_verified"))
        val c = controller(b)
        c.startGoal("tidy"); c.captureScene(); c.proceedToPlan(); c.beginStep(); c.verifyStep()
        assertFalse(c.app.value.stepVerified)
        c.acceptVerification() // must not advance or call plan again (plans queue is empty)
        assertEquals(AppScreen.VERIFICATION, c.app.value.screen)
        assertEquals(0, c.app.value.verifiedSteps)
        assertNotNull(c.app.value.notice)
    }

    @Test
    fun verifiedButLowConfidenceIsNotAccepted() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(stepReply)), verify = verified(0.6f))
        val c = controller(b)
        c.startGoal("tidy"); c.captureScene(); c.proceedToPlan(); c.beginStep(); c.verifyStep()
        assertFalse(c.app.value.stepVerified)
        assertEquals(MissionState.UNCERTAIN_REVIEW, c.vm.uiState.value.missionState)
    }

    @Test
    fun cannotTellAndUnknownStatusAreNeverSuccess() = runBlocking {
        for (status in listOf("cannot_tell", "something_new")) {
            val b = ScriptedBackend(plans = ArrayDeque(listOf(stepReply)), verify = verified(0.95f, status))
            val c = controller(b)
            c.startGoal("tidy"); c.captureScene(); c.proceedToPlan(); c.beginStep(); c.verifyStep()
            assertFalse(status, c.app.value.stepVerified)
            assertTrue(status, c.vm.uiState.value.latestVerificationResult?.isVerified == false)
        }
    }

    @Test
    fun blockedGoalShowsRefusalAndNeverOpensCamera() = runBlocking {
        val c = controller(ScriptedBackend(blocked = true))
        c.startGoal("inspect the wall outlet for loose wire")
        assertEquals(AppScreen.HOME, c.app.value.screen)
        assertEquals(MissionState.HAZARD_BLOCKED, c.vm.uiState.value.missionState)
        assertNotNull(c.vm.uiState.value.activeSafetyAlert)
        assertFalse(c.vm.uiState.value.activeSafetyAlert!!.overrideAllowed)
    }

    @Test
    fun hazardInSceneStopsBeforePlanning() = runBlocking {
        val b = ScriptedBackend(world = WorldInfo(listOf("cup"), listOf("smoke"), emptyList()))
        val c = controller(b) // plans queue empty: calling plan would throw
        c.startGoal("tidy"); c.captureScene()
        assertEquals(AppScreen.CAMERA, c.app.value.screen)
        assertNotNull(c.vm.uiState.value.activeSafetyAlert)
        assertTrue(c.vm.uiState.value.planSteps.isEmpty())
    }

    @Test
    fun nothingToDoIsNotReportedAsSuccess() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(PlanReply("no_action_needed", null, null, null))))
        val c = controller(b)
        c.startGoal("tidy"); c.captureScene()
        assertEquals(AppScreen.HOME, c.app.value.screen)
        assertNotEquals(AppScreen.COMPLETED, c.app.value.screen)
        assertTrue(c.app.value.notice!!.contains("nothing was verified"))
    }

    @Test
    fun needsObservationSendsUserBackToCamera() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(PlanReply("needs_observation", null, null, "retake"))))
        val c = controller(b)
        c.startGoal("tidy"); c.captureScene()
        assertEquals(AppScreen.CAMERA, c.app.value.screen)
        assertEquals("retake", c.app.value.notice)
    }

    @Test
    fun unknownPlanOutcomeIsNotSuccess() = runBlocking {
        val b = ScriptedBackend(plans = ArrayDeque(listOf(PlanReply("surprise", null, null, null))))
        val c = controller(b)
        c.startGoal("tidy"); c.captureScene()
        assertNotEquals(AppScreen.COMPLETED, c.app.value.screen)
        assertTrue(c.vm.uiState.value.planSteps.isEmpty())
    }

    @Test
    fun serverAndCameraErrorsBecomeNoticesNotResults() = runBlocking {
        val b = ScriptedBackend(failWith = ApiException(502, "perception unavailable"))
        val c = controller(b)
        c.startGoal("tidy")
        assertEquals("perception unavailable", c.app.value.notice)
        assertEquals(AppScreen.HOME, c.app.value.screen)

        val c2 = controller(ScriptedBackend(), FakeFrames(fail = true))
        c2.startGoal("tidy"); c2.captureScene()
        assertEquals("no camera", c2.app.value.notice)
        assertEquals(AppScreen.CAMERA, c2.app.value.screen)
        assertFalse(c2.app.value.busy)
    }

    @Test
    fun verifyWithoutSessionFailsSafely() = runBlocking {
        val c = controller(ScriptedBackend())
        c.verifyStep()
        assertNotNull(c.app.value.notice)
        assertNull(c.vm.uiState.value.latestVerificationResult)
    }

    @Test
    fun blankGoalIsRejectedLocally() = runBlocking {
        val c = controller(ScriptedBackend())
        c.startGoal("   ")
        assertEquals(AppScreen.HOME, c.app.value.screen)
        assertNotNull(c.app.value.notice)
    }
}

private fun assertNotEquals(unexpected: Any, actual: Any) = org.junit.Assert.assertNotEquals(unexpected, actual)

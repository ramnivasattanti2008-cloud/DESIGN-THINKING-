package com.mirror.mobile

import com.mirror.mobile.api.JsonParsing
import com.mirror.mobile.api.MirrorApi
import com.mirror.mobile.api.VerifyReply
import com.mirror.mobile.capture.FrameMetrics
import com.mirror.mobile.integration.BackendAdapter
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ParsingAndMetricsTest {

    @Test
    fun planReplyWithNullFieldsParses() {
        val p = JsonParsing.plan(JSONObject("""{"outcome":"needs_observation","done":false,"step":null,"gate":null,"message":"retake"}"""))
        assertEquals("needs_observation", p.outcome)
        assertNull(p.step); assertNull(p.gate)
        assertEquals("retake", p.message)
    }

    @Test
    fun nullMessageIsNullNotTheStringNull() {
        val p = JsonParsing.plan(JSONObject("""{"outcome":"completed","step":null,"gate":null,"message":null}"""))
        assertNull(p.message)
    }

    @Test
    fun stepPlanParses() {
        val p = JsonParsing.plan(JSONObject("""{"outcome":"step","message":null,
          "step":{"id":"s1","instruction":"Move the cup off the surface.","tier":"A1","tier_reason":"x","expected_evidence":["no cup visible"]},
          "gate":{"step_id":"s1","tier":"A1","decision":"allow","rule_id":"R-planner"}}"""))
        assertEquals("no cup visible", p.step!!.expectedEvidence.single())
        assertEquals("allow", p.gate!!.decision)
    }

    @Test
    fun verifyReplyParses() {
        val v = JsonParsing.verify(JSONObject("""{"step_id":"s1","status":"cannot_tell","evidence_seen":[],"evidence_missing":["x"],"frame_quality":"poor","confidence":0.0,"reason":"dark"}"""))
        assertEquals("cannot_tell", v.status); assertTrue(v.framePoor); assertEquals(0f, v.confidence, 0f)
    }

    @Test
    fun worldParsesLabelsAndHazards() {
        val w = JsonParsing.world(JSONObject("""{"observations":[{"label":"cup"},{"label":"lamp"}],"hazards":["smoke"],"unknowns":[]}"""))
        assertEquals(listOf("cup", "lamp"), w.labels); assertEquals(listOf("smoke"), w.hazards)
    }

    @Test
    fun errorDetailReadsFastApiShape() {
        assertEquals("perception unavailable: down", JsonParsing.errorDetail("""{"detail":"perception unavailable: down"}"""))
        assertEquals("plain", JsonParsing.errorDetail("plain"))
    }

    private fun reply(status: String, conf: Float) = VerifyReply("s", status, emptyList(), emptyList(), false, conf, "")

    @Test
    fun onlyVerifiedWithEnoughConfidencePasses() {
        assertTrue(BackendAdapter.isStepVerified(reply("verified", 0.85f)))
        assertFalse(BackendAdapter.isStepVerified(reply("verified", 0.84f)))
        assertFalse(BackendAdapter.isStepVerified(reply("not_verified", 0.99f)))
        assertFalse(BackendAdapter.isStepVerified(reply("cannot_tell", 0.99f)))
        assertFalse(BackendAdapter.isStepVerified(reply("", 1f)))
    }

    @Test
    fun adapterFlagsInterceptedFalseSuccess() {
        val low = BackendAdapter.verificationResult(reply("verified", 0.6f))
        assertFalse(low.isVerified)
        assertTrue(low.uncertaintyFactors.contains("Confidence below the required level"))
        assertTrue(BackendAdapter.verificationResult(reply("surprise", 1f)).uncertaintyFactors.contains("Unrecognised server status"))
    }

    @Test
    fun brightnessAndBlurMetrics() {
        val w = 16; val h = 16
        val flat = IntArray(w * h) { 128 }
        assertEquals(1f, FrameMetrics.blur(flat, w, h), 0f)            // no detail: treated as unusable
        val checker = IntArray(w * h) { if ((it % w + it / w) % 2 == 0) 0 else 255 }
        assertEquals(0f, FrameMetrics.blur(checker, w, h), 0f)         // maximum detail: sharp
        assertEquals(0.5f, FrameMetrics.brightness(flat), 0.01f)
        assertEquals(0f, FrameMetrics.brightness(IntArray(0)), 0f)
        assertEquals(1f, FrameMetrics.blur(IntArray(4), 2, 2), 0f)     // too small to judge
    }

    @Test
    fun apiKeyHeaderIsSentOnlyWhenAKeyIsConfigured() {
        assertTrue(MirrorApi.headersFor("").isEmpty())
        assertTrue(MirrorApi.headersFor("   ").isEmpty())
        assertEquals(mapOf("X-API-Key" to "abc"), MirrorApi.headersFor("  abc "))
    }
}

package com.mirror.mobile.api

import org.json.JSONArray
import org.json.JSONObject

/** Pure JSON <-> model mapping, kept separate from HTTP so it can be unit tested on the JVM. */
object JsonParsing {

    /** org.json turns a JSON null into the string "null" with optString, so check isNull first. */
    private fun JSONObject.str(key: String): String? = if (isNull(key)) null else getString(key)

    private fun JSONArray?.strings(): List<String> =
        if (this == null) emptyList() else List(length()) { getString(it) }

    fun session(o: JSONObject) = SessionInfo(
        sessionId = o.getString("session_id"),
        interpretedIntent = o.optString("interpreted_intent", ""),
        blocked = o.optBoolean("blocked", false),
        message = o.str("message")
    )

    fun world(o: JSONObject): WorldInfo {
        val obs = o.optJSONArray("observations")
        val labels = if (obs == null) emptyList() else List(obs.length()) { obs.getJSONObject(it).getString("label") }
        return WorldInfo(labels, o.optJSONArray("hazards").strings(), o.optJSONArray("unknowns").strings())
    }

    fun plan(o: JSONObject): PlanReply {
        val step = if (o.isNull("step")) null else o.getJSONObject("step").let {
            BackendStep(
                id = it.getString("id"),
                instruction = it.getString("instruction"),
                tier = it.getString("tier"),
                tierReason = it.optString("tier_reason", ""),
                expectedEvidence = it.optJSONArray("expected_evidence").strings()
            )
        }
        val gate = if (o.isNull("gate")) null else o.getJSONObject("gate").let {
            BackendGate(it.getString("tier"), it.getString("decision"), it.getString("rule_id"))
        }
        return PlanReply(o.getString("outcome"), step, gate, o.str("message"))
    }

    fun verify(o: JSONObject) = VerifyReply(
        stepId = o.getString("step_id"),
        status = o.getString("status"),
        evidenceSeen = o.optJSONArray("evidence_seen").strings(),
        evidenceMissing = o.optJSONArray("evidence_missing").strings(),
        framePoor = o.optString("frame_quality", "ok") == "poor",
        confidence = o.optDouble("confidence", 0.0).toFloat(),
        reason = o.optString("reason", "")
    )

    fun framesBody(frames: List<FrameUpload>): JSONObject = JSONObject().put(
        "frames",
        JSONArray().also { arr ->
            frames.forEach {
                arr.put(
                    JSONObject()
                        .put("id", it.id)
                        .put("blur", it.blur.toDouble())
                        .put("brightness", it.brightness.toDouble())
                        .put("data_b64", it.jpegBase64)
                        .put("media_type", "image/jpeg")
                )
            }
        }
    )

    /** FastAPI errors look like {"detail": "..."}; fall back to the raw text. */
    fun errorDetail(text: String): String =
        runCatching { JSONObject(text).opt("detail")?.toString() }.getOrNull()?.takeIf { it.isNotBlank() } ?: text.take(200)
}

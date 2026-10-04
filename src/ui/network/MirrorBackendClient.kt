package com.mirror.ui.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Production-ready HTTP client for the MIRROR FastAPI backend (/v1 endpoints).
 * Directly maps to CreateSessionResponse, WorldStateDto, PlanResponse, and VerifyResultDto.
 */
class MirrorBackendClient(
    private val baseUrl: String = "http://10.0.2.2:8000" // Android emulator loopback or localhost
) {
    suspend fun healthCheck(): Result<Boolean> = withContext(Dispatchers.IO) {
        runCatching {
            val res = httpGet("$baseUrl/v1/health")
            val json = JSONObject(res)
            json.optBoolean("ok", false)
        }
    }

    suspend fun createSession(goal: String): Result<CreateSessionResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val payload = JSONObject().put("goal", goal).toString()
            val raw = httpPost("$baseUrl/v1/sessions", payload)
            val json = JSONObject(raw)

            val gateObj = json.getJSONObject("goal_gate")
            val gateDto = GateDecisionDto(
                step_id = gateObj.getString("step_id"),
                tier = gateObj.getString("tier"),
                decision = gateObj.getString("decision"),
                rule_id = gateObj.getString("rule_id")
            )

            CreateSessionResponse(
                session_id = json.getString("session_id"),
                interpreted_intent = json.getString("interpreted_intent"),
                goal_gate = gateDto,
                blocked = json.getBoolean("blocked"),
                message = json.optString("message", null)
            )
        }
    }

    suspend fun observe(sessionId: String, frames: List<FrameDto>): Result<WorldStateDto> = withContext(Dispatchers.IO) {
        runCatching {
            val framesArr = JSONArray()
            frames.forEach { f ->
                val fObj = JSONObject()
                    .put("id", f.id)
                    .put("blur", f.blur.toDouble())
                    .put("brightness", f.brightness.toDouble())
                    .put("media_type", f.media_type)
                if (f.data_b64 != null) fObj.put("data_b64", f.data_b64)
                if (f.fake_labels.isNotEmpty()) {
                    val lbls = JSONArray()
                    f.fake_labels.forEach { lbls.put(it) }
                    fObj.put("fake_labels", lbls)
                }
                framesArr.put(fObj)
            }
            val payload = JSONObject().put("frames", framesArr).toString()
            val raw = httpPost("$baseUrl/v1/sessions/$sessionId/observe", payload)
            val json = JSONObject(raw)

            val obsList = mutableListOf<ObservationDto>()
            val obsArr = json.optJSONArray("observations") ?: JSONArray()
            for (i in 0 until obsArr.length()) {
                val o = obsArr.getJSONObject(i)
                obsList.add(
                    ObservationDto(
                        id = o.getString("id"),
                        label = o.getString("label"),
                        confidence = o.getDouble("confidence").toFloat(),
                        where_hint = o.optString("where_hint", ""),
                        source_frame = o.getString("source_frame")
                    )
                )
            }

            val unknowns = mutableListOf<String>()
            val unkArr = json.optJSONArray("unknowns") ?: JSONArray()
            for (i in 0 until unkArr.length()) unknowns.add(unkArr.getString(i))

            val hazards = mutableListOf<String>()
            val hazArr = json.optJSONArray("hazards") ?: JSONArray()
            for (i in 0 until hazArr.length()) hazards.add(hazArr.getString(i))

            WorldStateDto(
                session_id = json.getString("session_id"),
                observations = obsList,
                unknowns = unknowns,
                hazards = hazards
            )
        }
    }

    suspend fun plan(sessionId: String): Result<PlanResponse> = withContext(Dispatchers.IO) {
        runCatching {
            val raw = httpPost("$baseUrl/v1/sessions/$sessionId/plan", "{}")
            val json = JSONObject(raw)

            var stepDto: StepDto? = null
            if (!json.isNull("step")) {
                val s = json.getJSONObject("step")
                val evList = mutableListOf<String>()
                val evArr = s.optJSONArray("expected_evidence") ?: JSONArray()
                for (i in 0 until evArr.length()) evList.add(evArr.getString(i))

                stepDto = StepDto(
                    id = s.getString("id"),
                    instruction = s.getString("instruction"),
                    tier = s.getString("tier"),
                    tier_reason = s.optString("tier_reason", ""),
                    expected_evidence = evList,
                    rollback_hint = s.optString("rollback_hint", null)
                )
            }

            var gateDto: GateDecisionDto? = null
            if (!json.isNull("gate")) {
                val g = json.getJSONObject("gate")
                gateDto = GateDecisionDto(
                    step_id = g.getString("step_id"),
                    tier = g.getString("tier"),
                    decision = g.getString("decision"),
                    rule_id = g.getString("rule_id")
                )
            }

            PlanResponse(
                outcome = json.getString("outcome"),
                done = json.getBoolean("done"),
                step = stepDto,
                gate = gateDto,
                message = json.optString("message", null)
            )
        }
    }

    suspend fun verify(sessionId: String, frames: List<FrameDto>): Result<VerifyResultDto> = withContext(Dispatchers.IO) {
        runCatching {
            val framesArr = JSONArray()
            frames.forEach { f ->
                val fObj = JSONObject()
                    .put("id", f.id)
                    .put("blur", f.blur.toDouble())
                    .put("brightness", f.brightness.toDouble())
                if (f.data_b64 != null) fObj.put("data_b64", f.data_b64)
                if (f.fake_labels.isNotEmpty()) {
                    val lbls = JSONArray()
                    f.fake_labels.forEach { lbls.put(it) }
                    fObj.put("fake_labels", lbls)
                }
                framesArr.put(fObj)
            }
            val payload = JSONObject().put("frames", framesArr).toString()
            val raw = httpPost("$baseUrl/v1/sessions/$sessionId/verify", payload)
            val json = JSONObject(raw)

            val seen = mutableListOf<String>()
            val sArr = json.optJSONArray("evidence_seen") ?: JSONArray()
            for (i in 0 until sArr.length()) seen.add(sArr.getString(i))

            val missing = mutableListOf<String>()
            val mArr = json.optJSONArray("evidence_missing") ?: JSONArray()
            for (i in 0 until mArr.length()) missing.add(mArr.getString(i))

            VerifyResultDto(
                step_id = json.getString("step_id"),
                status = json.getString("status"),
                evidence_seen = seen,
                evidence_missing = missing,
                frame_quality = json.optString("frame_quality", "ok"),
                confidence = json.optDouble("confidence", 0.0).toFloat(),
                reason = json.optString("reason", "")
            )
        }
    }

    suspend fun getSession(sessionId: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            httpGet("$baseUrl/v1/sessions/$sessionId")
        }
    }

    private fun httpGet(urlStr: String): String {
        val url = URL(urlStr)
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.connectTimeout = 3000
        conn.readTimeout = 3000

        val code = conn.responseCode
        if (code in 200..299) {
            return conn.inputStream.bufferedReader().use(BufferedReader::readText)
        } else {
            val err = conn.errorStream?.bufferedReader()?.use(BufferedReader::readText) ?: "HTTP $code"
            throw RuntimeException("Backend GET error $code: $err")
        }
    }

    private fun httpPost(urlStr: String, body: String): String {
        val url = URL(urlStr)
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.connectTimeout = 3000
        conn.readTimeout = 4000
        conn.doOutput = true

        OutputStreamWriter(conn.outputStream).use { writer ->
            writer.write(body)
            writer.flush()
        }

        val code = conn.responseCode
        if (code in 200..299) {
            return conn.inputStream.bufferedReader().use(BufferedReader::readText)
        } else {
            val err = conn.errorStream?.bufferedReader()?.use(BufferedReader::readText) ?: "HTTP $code"
            throw RuntimeException("Backend POST error $code: $err")
        }
    }
}


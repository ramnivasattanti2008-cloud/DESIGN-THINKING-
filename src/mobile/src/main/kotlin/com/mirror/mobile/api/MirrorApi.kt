package com.mirror.mobile.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** HTTP client for the MIRROR backend. Every failure becomes an [ApiException]. */
class MirrorApi(private val baseUrl: String) : Backend {

    override suspend fun createSession(goal: String): SessionInfo =
        JsonParsing.session(call("POST", "/v1/sessions", JSONObject().put("goal", goal)))

    override suspend fun observe(sessionId: String, frames: List<FrameUpload>): WorldInfo =
        JsonParsing.world(call("POST", "/v1/sessions/$sessionId/observe", JsonParsing.framesBody(frames)))

    override suspend fun plan(sessionId: String): PlanReply =
        JsonParsing.plan(call("POST", "/v1/sessions/$sessionId/plan", null))

    override suspend fun verify(sessionId: String, frames: List<FrameUpload>): VerifyReply =
        JsonParsing.verify(call("POST", "/v1/sessions/$sessionId/verify", JsonParsing.framesBody(frames)))

    private suspend fun call(method: String, path: String, body: JSONObject?): JSONObject =
        withContext(Dispatchers.IO) {
            val conn = URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection
            try {
                conn.requestMethod = method
                conn.connectTimeout = 10_000
                conn.readTimeout = 90_000 // a model call can be slow
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("Accept", "application/json")
                if (body != null) {
                    conn.doOutput = true
                    conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                }
                val code = conn.responseCode
                val stream = if (code < 400) conn.inputStream else conn.errorStream
                val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                if (code >= 400) throw ApiException(code, JsonParsing.errorDetail(text))
                JSONObject(text)
            } catch (e: IOException) {
                throw ApiException(null, "Cannot reach the MIRROR server (${e.javaClass.simpleName}).")
            } catch (e: JSONException) {
                throw ApiException(null, "The MIRROR server sent a reply the app cannot read.")
            } finally {
                conn.disconnect()
            }
        }
}

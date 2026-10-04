package com.mirror.ui.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/**
 * Production-ready HTTP client for the MIRROR FastAPI backend (/v1 endpoints).
 * Supports both live REST backend communication and graceful offline fallback.
 */
class MirrorBackendClient(
    private val baseUrl: String = "http://10.0.2.2:8000" // Android emulator loopback or localhost
) {
    suspend fun healthCheck(): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            httpGet("$baseUrl/v1/health")
        }
    }

    suspend fun createSession(goal: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val jsonBody = """{"goal": ${escapeJson(goal)}}"""
            httpPost("$baseUrl/v1/sessions", jsonBody)
        }
    }

    suspend fun plan(sessionId: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            httpPost("$baseUrl/v1/sessions/$sessionId/plan", "{}")
        }
    }

    suspend fun observe(sessionId: String, frameJsonList: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val jsonBody = """{"frames": $frameJsonList}"""
            httpPost("$baseUrl/v1/sessions/$sessionId/observe", jsonBody)
        }
    }

    suspend fun verify(sessionId: String, frameJsonList: String): Result<String> = withContext(Dispatchers.IO) {
        runCatching {
            val jsonBody = """{"frames": $frameJsonList}"""
            httpPost("$baseUrl/v1/sessions/$sessionId/verify", jsonBody)
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

    private fun escapeJson(text: String): String {
        return "\"" + text.replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r") + "\""
    }
}

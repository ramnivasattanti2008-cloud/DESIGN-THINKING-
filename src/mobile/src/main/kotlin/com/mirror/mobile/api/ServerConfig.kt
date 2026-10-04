package com.mirror.mobile.api

/**
 * Where the app talks to. It can be changed at run time (Server button on the start screen) so a
 * phone test does not need a rebuild each time the PC address changes.
 */
data class ServerConfig(val baseUrl: String, val apiKey: String = "") {

    companion object {
        private val URL_SHAPE = Regex(
            """^(https?)://([A-Za-z0-9.\-]+|\[[0-9A-Fa-f:]+\])(:(\d{1,5}))?(/[^\s?#]*)?$""",
            RegexOption.IGNORE_CASE
        )

        /** A clean base URL (no trailing slash), or null if [raw] is not an http(s) address with a host. */
        fun cleanUrl(raw: String): String? {
            val trimmed = raw.trim().trimEnd('/')
            val m = URL_SHAPE.matchEntire(trimmed) ?: return null
            val port = m.groupValues[4]
            if (port.isNotEmpty() && port.toInt() !in 1..65535) return null
            return trimmed
        }

        /**
         * A message for the person when [raw] cannot be used, or null if it is fine. Plain http is only
         * allowed when [allowHttp] is true (debug builds on a local network); a release build needs https.
         */
        fun problem(raw: String, allowHttp: Boolean): String? {
            val clean = cleanUrl(raw)
                ?: return "Enter an address like https://my-server:8443 or http://192.168.1.20:8000"
            if (!allowHttp && clean.startsWith("http://", ignoreCase = true)) {
                return "This build only talks to https:// servers."
            }
            return null
        }
    }
}

/** Where the settings live. The Android implementation stores them on the phone. */
interface ServerSettings {
    fun current(): ServerConfig
    fun save(config: ServerConfig)
}

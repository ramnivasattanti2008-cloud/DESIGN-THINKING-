package com.mirror.mobile.app

import android.content.Context
import com.mirror.mobile.api.ServerConfig
import com.mirror.mobile.api.ServerSettings

/**
 * Keeps the server address and the optional API key on the phone, falling back to the values the
 * app was built with. Development convenience: a key stored in the app can be extracted, and the
 * manifest turns backups off so it is not copied to the cloud.
 */
class AndroidServerSettings(context: Context, private val defaults: ServerConfig) : ServerSettings {

    private val prefs = context.getSharedPreferences("mirror_server", Context.MODE_PRIVATE)

    override fun current(): ServerConfig = ServerConfig(
        baseUrl = prefs.getString(KEY_URL, null)?.takeIf { it.isNotBlank() } ?: defaults.baseUrl,
        apiKey = prefs.getString(KEY_API, null) ?: defaults.apiKey
    )

    override fun save(config: ServerConfig) {
        prefs.edit().putString(KEY_URL, config.baseUrl).putString(KEY_API, config.apiKey).apply()
    }

    private companion object {
        const val KEY_URL = "base_url"
        const val KEY_API = "api_key"
    }
}

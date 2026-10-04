package com.mirror.mobile

import com.mirror.mobile.api.ServerConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ServerConfigTest {

    @Test
    fun cleanUrlAcceptsHttpAndHttpsAddressesAndTrimsTheTrailingSlash() {
        assertEquals("http://192.168.1.20:8000", ServerConfig.cleanUrl("  http://192.168.1.20:8000/ "))
        assertEquals("https://mirror.example.com", ServerConfig.cleanUrl("https://mirror.example.com"))
        assertEquals("http://10.0.2.2:8000", ServerConfig.cleanUrl("http://10.0.2.2:8000"))
        assertEquals("https://example.com:8443/api", ServerConfig.cleanUrl("https://example.com:8443/api/"))
        assertEquals("http://[::1]:8000", ServerConfig.cleanUrl("http://[::1]:8000"))
    }

    @Test
    fun cleanUrlRejectsAnythingElse() {
        for (bad in listOf("", "   ", "192.168.1.20:8000", "ftp://host", "http://", "http:///x", "http://ho st",
            "http://host:0", "http://host:99999", "http://host?x=1", "javascript:alert(1)", "file:///etc/passwd")) {
            assertNull("should be rejected: $bad", ServerConfig.cleanUrl(bad))
        }
    }

    @Test
    fun releaseBuildsRefusePlainHttpButDebugBuildsAllowIt() {
        assertNull(ServerConfig.problem("http://192.168.1.20:8000", allowHttp = true))
        assertNotNull(ServerConfig.problem("http://192.168.1.20:8000", allowHttp = false))
        assertNull(ServerConfig.problem("https://mirror.example.com", allowHttp = false))
        assertNotNull(ServerConfig.problem("not a url", allowHttp = true))
    }
}

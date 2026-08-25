package com.example.campusai.ui.screens.profile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EduLoginSecurityTest {
    @Test
    fun navigationAcceptsOnlyExactHttpsLoginOrBackendAllowedOrigins() {
        val loginUrl = "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"

        assertTrue(isAllowedEduNavigation("https://xk.huel.edu.cn/jwglxt/xsxx", loginUrl))
        assertTrue(isAllowedEduNavigation("https://sso.huel.edu.cn/cas/login", loginUrl, listOf("https://sso.huel.edu.cn")))
        assertFalse(isAllowedEduNavigation("http://xk.huel.edu.cn/jwglxt", loginUrl))
        assertFalse(isAllowedEduNavigation("https://xk.huel.edu.cn.attacker.example/login", loginUrl))
        assertFalse(isAllowedEduNavigation("weixin://dl/business", loginUrl))
    }

    @Test
    fun requestLayerFailsClosedForExternalAndMissingUrls() {
        val loginUrl = "https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html"
        assertFalse(shouldBlockEduRequest("https://xk.huel.edu.cn/jwglxt/main", loginUrl))
        assertTrue(shouldBlockEduRequest("https://xk.huel.edu.cn.attacker.example/post", loginUrl))
        assertTrue(shouldBlockEduRequest(null, loginUrl))
    }

    @Test
    fun cookieDtosKeepSameNameFromDifferentAllowedOrigins() {
        val portal = cookieDtosForUrl("JSESSIONID=portal", "https://xk.huel.edu.cn/jwglxt")
        val sso = cookieDtosForUrl("JSESSIONID=sso", "https://sso.huel.edu.cn/cas")

        assertEquals(2, (portal + sso).size)
        assertEquals(listOf("xk.huel.edu.cn", "sso.huel.edu.cn"), (portal + sso).map { it.domain })
        assertTrue((portal + sso).all { it.secure == null && it.http_only == null && it.path == null })
    }
}

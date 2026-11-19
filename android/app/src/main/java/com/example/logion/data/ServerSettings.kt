package com.example.logion.data

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import okhttp3.HttpUrl

// ==============================
// 보드(서버) 주소 설정
// 더보기 화면에서 입력·저장. 앱을 다시 켜도 남음 (SharedPreferences)
// ==============================

/** 폰 USB 테더링에서 보드가 받는 주소의 예. 실제 주소는 보드에서 `hostname -I` 로 확인해 더보기에서 바꾼다. */
const val DEFAULT_BASE_URL = "http://192.168.42.129:8000/"

/**
 * 사람이 입력한 주소를 Retrofit 이 쓰는 모양으로: "192.168.0.2" → "http://192.168.0.2:8000/".
 * 포트를 안 쓰면 8000, 끝에 '/' 를 붙인다. 주소가 아니면 null.
 */
fun normalizeBaseUrl(input: String): String? {
    var s = input.trim()
    if (s.isEmpty()) return null
    if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
    val url = HttpUrl.parse(s) ?: return null
    val hasPort = Regex("^https?://[^/]+:[0-9]+").containsMatchIn(s)
    val b = url.newBuilder()
    if (!hasPort) b.port(8000)
    val path = url.encodedPath().trimEnd('/') + "/"
    return b.encodedPath(path).build().toString()
}

object ServerSettings {
    private const val PREFS = "logion_settings"
    private const val KEY_BASE_URL = "base_url"

    private var prefs: SharedPreferences? = null

    var baseUrl by mutableStateOf(DEFAULT_BASE_URL)
        private set

    fun init(context: Context) {
        val p = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs = p
        baseUrl = p.getString(KEY_BASE_URL, null)?.let(::normalizeBaseUrl) ?: DEFAULT_BASE_URL
    }

    /** 저장하고 정리된 주소를 돌려줌. 주소 모양이 아니면 null (저장 안 함). */
    fun save(input: String): String? {
        val url = normalizeBaseUrl(input) ?: return null
        prefs?.edit()?.putString(KEY_BASE_URL, url)?.apply()
        baseUrl = url
        return url
    }
}

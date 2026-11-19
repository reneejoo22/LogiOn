package com.example.logion.data.remote

import com.example.logion.data.ServerSettings
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

// ==============================
// Retrofit 설정
// 서버 = 오렌지파이 보드 (STT·LLM·TTS·백엔드·DB). 주소는 더보기 화면에서 바꿈 (ServerSettings)
// ==============================

object RetrofitClient {

    // 녹음 업로드 → STT → LLM → TTS 가 보드에서 최대 3.5초쯤, LLM 제한 시간 8초. 넉넉히 20초
    const val TIMEOUT_SECONDS = 20L

    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .callTimeout(TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .build()

    @Volatile private var cachedUrl: String? = null
    @Volatile private var cachedApi: LogiOnApi? = null

    /** 지금 설정된 보드 주소 (끝이 '/') */
    val baseUrl: String get() = ServerSettings.baseUrl

    /** 주소가 바뀌면 새로 만든다 */
    val api: LogiOnApi
        get() {
            val url = baseUrl
            synchronized(this) {
                val a = cachedApi
                if (a != null && url == cachedUrl) return a
                val made = Retrofit.Builder()
                    .baseUrl(url)
                    .client(http)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build()
                    .create(LogiOnApi::class.java)
                cachedApi = made
                cachedUrl = url
                return made
            }
        }

    /** 서버가 준 "/api/assistant/voice/audio/…" 를 전체 주소로 */
    fun fullUrl(path: String): String = baseUrl.trimEnd('/') + "/" + path.trimStart('/')
}

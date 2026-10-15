package com.example.logion.data.remote

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

// ==============================
// Retrofit 설정
// 백엔드 서버 주소와 API 통신 객체를 관리
// ==============================

object RetrofitClient {

    // Android 에뮬레이터에서 PC의 localhost에 접속할 때 사용하는 주소
    private const val BASE_URL = "http://10.0.2.2:8000/"

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val api: LogiOnApi = retrofit.create(LogiOnApi::class.java)
}
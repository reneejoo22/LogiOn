package com.example.logion.speech

import android.media.AudioAttributes
import android.media.MediaPlayer
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlin.coroutines.resume

// ==============================
// 보드가 만든 응답 음성(wav) 재생. URL 을 MediaPlayer 가 바로 받음
// ==============================

object AudioPlayer {
    private const val TAG = "AUDIO_PLAY"
    private var player: MediaPlayer? = null
    private var finish: (() -> Unit)? = null

    /** 끝날 때까지 기다림. stop() 이나 코루틴 취소로 바로 끝남 */
    suspend fun play(url: String) = withContext(Dispatchers.Main) {
        stop()
        suspendCancellableCoroutine<Unit> { cont ->
            val mp = MediaPlayer()
            var done = false
            fun end() {
                if (done) return
                done = true
                if (player === mp) {
                    player = null
                    finish = null
                }
                runCatching { mp.release() }
                if (cont.isActive) cont.resume(Unit)
            }
            player = mp
            finish = ::end
            try {
                mp.setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                mp.setOnPreparedListener { it.start() }
                mp.setOnCompletionListener { end() }
                mp.setOnErrorListener { _, what, extra ->
                    Log.e(TAG, "재생 실패 what=$what extra=$extra $url")
                    end()
                    true
                }
                mp.setDataSource(url)
                mp.prepareAsync()
            } catch (e: Exception) {
                Log.e(TAG, "재생 준비 실패 $url", e)
                end()
            }
            cont.invokeOnCancellation { runCatching { mp.stop() }; end() }
        }
    }

    /** 읽기 멈춤 */
    fun stop() {
        val f = finish
        runCatching { player?.stop() }
        f?.invoke()
    }
}

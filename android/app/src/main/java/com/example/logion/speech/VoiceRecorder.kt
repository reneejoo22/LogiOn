package com.example.logion.speech

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext

// ==============================
// 녹음만 하는 곳 (STT 는 보드에서)
// 16kHz mono PCM16. 멈춤: 말이 끝나고 1초 조용 / 🎤 다시 누름 / 10초 / 6초 동안 말이 없음
// ==============================

class VoiceRecorder {
    companion object {
        const val SAMPLE_RATE = 16000
        private const val FRAME = SAMPLE_RATE / 50          // 20ms
        private const val TAG = "VOICE_REC"
    }

    @Volatile private var stopRequested = false

    /** 🎤 다시 누름: 지금까지 녹음한 것으로 끝냄 */
    fun stop() {
        stopRequested = true
    }

    /** 녹음한 PCM. 마이크를 못 열면 null. onLevel: 0~1 입력 크기 (화면 막대용) */
    @SuppressLint("MissingPermission") // 버튼에서 rememberMicAction 으로 권한을 받은 뒤에만 부름
    suspend fun record(
        onLevel: (Float) -> Unit = {},
        maxSeconds: Int = 10,
        noSpeechSeconds: Int = 6,
        silenceMs: Int = 1000,
    ): ShortArray? = withContext(Dispatchers.IO) {
        stopRequested = false
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION, SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, SAMPLE_RATE)
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            Log.e(TAG, "AudioRecord 초기화 실패")
            return@withContext null
        }
        val out = ShortArray(SAMPLE_RATE * maxSeconds)
        var n = 0
        val frame = ShortArray(FRAME)
        val eos = EndOfSpeech(frameMs = 20, silenceMs = silenceMs)
        try {
            record.startRecording()
            while (coroutineContext.isActive && !stopRequested && n < out.size) {
                val got = record.read(frame, 0, minOf(FRAME, out.size - n))
                if (got <= 0) continue
                System.arraycopy(frame, 0, out, n, got)
                n += got
                val level = rms(frame, got)
                onLevel((level * 6f).coerceAtMost(1f))
                if (eos.push(level)) break
                if (!eos.heardSpeech && n >= SAMPLE_RATE * noSpeechSeconds) break
            }
        } finally {
            runCatching { record.stop() }
            record.release()
            onLevel(0f)
        }
        Log.d(TAG, "녹음 ${n * 1000 / SAMPLE_RATE}ms, 말 들림=${eos.heardSpeech}, 버튼 멈춤=$stopRequested")
        out.copyOf(n)
    }
}

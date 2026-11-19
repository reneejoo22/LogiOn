package com.example.logion.speech

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** 16bit PCM(mono) → wav 파일 바이트 (44바이트 헤더 + 데이터). 보드 /api/assistant/voice 에 올림 */
fun pcmToWav(pcm: ShortArray, sampleRate: Int = VoiceRecorder.SAMPLE_RATE): ByteArray {
    val data = ByteBuffer.allocate(pcm.size * 2).order(ByteOrder.LITTLE_ENDIAN)
    pcm.forEach { data.putShort(it) }
    val bytes = data.array()
    val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
    h.put("RIFF".toByteArray()).putInt(36 + bytes.size).put("WAVE".toByteArray())
    h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1)       // PCM, mono
        .putInt(sampleRate).putInt(sampleRate * 2).putShort(2).putShort(16)
    h.put("data".toByteArray()).putInt(bytes.size)
    return h.array() + bytes
}

/** 20ms 한 토막의 크기 (0~1, RMS) */
fun rms(frame: ShortArray, n: Int = frame.size): Float {
    if (n <= 0) return 0f
    var sum = 0.0
    for (i in 0 until n) {
        val v = frame[i] / 32768.0
        sum += v * v
    }
    return Math.sqrt(sum / n).toFloat()
}

/**
 * 말이 끝났는지 보는 크기 기준 (보드가 VAD 로 앞뒤 무음을 다시 자르므로 대략이면 충분).
 * 처음 0.3초로 주변 소음 크기를 재고, 그보다 3배(최소 0.015) 큰 토막이 3번(60ms) 이어지면 말 시작,
 * 말 시작 뒤 그보다 작은 토막이 silenceMs 이어지면 끝.
 */
class EndOfSpeech(private val frameMs: Int = 20, private val silenceMs: Int = 1000) {
    private var frames = 0
    private var noise = 0f
    private var loud = 0
    private var quiet = 0
    var heardSpeech = false
        private set

    /** 한 토막 넣고, 말이 끝났으면 true */
    fun push(level: Float): Boolean {
        frames++
        val warmup = 300 / frameMs
        if (frames <= warmup) {
            noise += level / warmup          // 처음 0.3초 평균 = 주변 소음
            return false
        }
        val threshold = (noise * 3f).coerceIn(0.015f, 0.08f)   // 바로 말을 시작해 소음이 크게 잡혀도 0.08 까지만
        if (!heardSpeech) {
            loud = if (level > threshold) loud + 1 else 0
            if (loud >= 3) heardSpeech = true
            return false
        }
        quiet = if (level < threshold) quiet + 1 else 0
        return quiet * frameMs >= silenceMs
    }
}

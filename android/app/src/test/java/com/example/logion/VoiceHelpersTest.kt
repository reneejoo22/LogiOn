package com.example.logion

import com.example.logion.data.normalizeBaseUrl
import com.example.logion.speech.EndOfSpeech
import com.example.logion.speech.pcmToWav
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

class VoiceHelpersTest {
    @Test
    fun wavHeaderIs16kMono16bit() {
        val wav = pcmToWav(ShortArray(16000) { 1000 })
        val b = ByteBuffer.wrap(wav).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(44 + 32000, wav.size)
        assertArrayEquals("RIFF".toByteArray(), wav.copyOfRange(0, 4))
        assertArrayEquals("WAVE".toByteArray(), wav.copyOfRange(8, 12))
        assertEquals(1, b.getShort(22).toInt())        // mono
        assertEquals(16000, b.getInt(24))              // sample rate
        assertEquals(16, b.getShort(34).toInt())       // bits
        assertEquals(32000, b.getInt(40))              // data size
        assertEquals(1000, b.getShort(44).toInt())
    }

    @Test
    fun baseUrlIsNormalized() {
        assertEquals("http://192.168.42.129:8000/", normalizeBaseUrl("192.168.42.129"))
        assertEquals("http://192.168.0.2:8000/", normalizeBaseUrl(" http://192.168.0.2:8000 "))
        assertEquals("http://10.0.2.2:9000/", normalizeBaseUrl("10.0.2.2:9000/"))
        assertNull(normalizeBaseUrl(""))
        assertNull(normalizeBaseUrl("http://"))
    }

    @Test
    fun endOfSpeechStopsAfterOneSecondOfQuiet() {
        val e = EndOfSpeech(frameMs = 20, silenceMs = 1000)
        repeat(15) { assertFalse(e.push(0.002f)) }      // 0.3초 주변 소음
        repeat(50) { assertFalse(e.push(0.2f)) }        // 1초 말
        assertTrue(e.heardSpeech)
        repeat(49) { assertFalse(e.push(0.002f)) }
        assertTrue(e.push(0.002f))                      // 1초 조용 → 끝
    }

    @Test
    fun noSpeechNeverEnds() {
        val e = EndOfSpeech()
        repeat(500) { assertFalse(e.push(0.003f)) }     // 말이 없으면 크기 기준으로는 안 끝남 (녹음기가 6초에 끊음)
        assertFalse(e.heardSpeech)
    }
}

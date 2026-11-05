package com.example.logion.speech

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.res.AssetManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.util.Log
import com.k2fsa.sherpa.onnx.OfflineRecognizer
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.Vad
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

// ==============================
// 온디바이스 STT / TTS 엔진 (sherpa-onnx)
//   listen()     : 마이크 → VAD 로 말한 구간 잘라냄 → 샘플
//   transcribe() : 샘플 → 글자 (SenseVoice)
//   speak()      : 글자 → 문장별 생성 → 바로 재생 (VITS)
// 프로젝트와 무관하게 아무 화면/텍스트에서나 쓸 수 있음
// ==============================

object SpeechEngine {
    private const val TAG = "SPEECH"

    sealed interface Status {
        data object Loading : Status
        data object Ready : Status
        data class Failed(val message: String) : Status
    }

    private val _status = MutableStateFlow<Status>(Status.Loading)
    val status: StateFlow<Status> = _status

    private var vad: Vad? = null
    private var recognizer: OfflineRecognizer? = null
    private var tts: OfflineTts? = null

    // sherpa 객체는 동시에 쓰면 안 돼서 하나씩
    private val sttLock = Mutex()
    private val ttsLock = Mutex()
    private val initLock = Mutex()

    @Volatile private var stopListeningRequested = false
    @Volatile private var stopSpeakingRequested = false
    @Volatile private var audioTrack: AudioTrack? = null

    // ------------------------------------------------------------ 초기화
    suspend fun init(context: Context) = initLock.withLock {
        if (_status.value == Status.Ready) return@withLock
        _status.value = Status.Loading
        withContext(Dispatchers.Default) {
            try {
                val app = context.applicationContext
                val am = app.assets
                val t0 = System.currentTimeMillis()

                vad = Vad(assetManager = am, config = getVadModelConfig())
                recognizer = OfflineRecognizer(assetManager = am, config = getSenseVoiceConfig())
                val espeakDir = copyAssetDir(am, "$TTS_MODEL_DIR/espeak-ng-data", app.filesDir)
                tts = OfflineTts(assetManager = am, config = getTtsConfig(espeakDir))

                Log.d(TAG, "모델 로딩 완료 ${System.currentTimeMillis() - t0}ms")
                _status.value = Status.Ready

                if (app.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0) selfTest()
            } catch (e: Throwable) {
                Log.e(TAG, "모델 로딩 실패", e)
                _status.value = Status.Failed(e.message ?: e.javaClass.simpleName)
            }
        }
    }

    val isReady get() = _status.value == Status.Ready

    // ------------------------------------------------------------ STT
    /** 마이크로 한 문장 듣기. 말이 끝나면(VAD) / stopListening() / maxSeconds 에서 멈춤. */
    @SuppressLint("MissingPermission") // 호출 전에 화면에서 RECORD_AUDIO 권한 확인
    suspend fun listen(
        maxSeconds: Float = 10f,
        onLevel: (Float) -> Unit = {},
    ): FloatArray? = withContext(Dispatchers.IO) {
        val v = vad ?: return@withContext null
        stopListeningRequested = false

        val minBuf = AudioRecord.getMinBufferSize(
            STT_SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION, STT_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            throw IllegalStateException("마이크를 열 수 없습니다")
        }

        val window = 512
        val pcm = ShortArray(window)
        val all = ArrayList<Float>(STT_SAMPLE_RATE * 10)
        var segment: FloatArray? = null
        sttLock.withLock { v.reset() }

        record.startRecording()
        try {
            val maxSamples = (maxSeconds * STT_SAMPLE_RATE).toInt()
            while (isActive && !stopListeningRequested && all.size < maxSamples) {
                val n = record.read(pcm, 0, window)
                if (n <= 0) continue
                val buf = FloatArray(n) { pcm[it] / 32768f }
                all.addAll(buf.asList())
                onLevel(buf.maxOf { kotlin.math.abs(it) })

                sttLock.withLock {
                    v.acceptWaveform(buf)
                    if (!v.empty()) { // 말 한 구간이 끝남
                        segment = v.front().samples
                        v.clear()
                    }
                }
                if (segment != null) break
            }
        } finally {
            record.stop()
            record.release()
        }

        // 버튼으로 끊었거나 시간이 다 된 경우: VAD 에 남은 말 / 없으면 녹음 전체
        segment ?: sttLock.withLock {
            v.flush()
            val s = if (!v.empty()) v.front().samples else null
            v.clear()
            s
        } ?: all.toFloatArray().takeIf { it.size > STT_SAMPLE_RATE / 4 }
    }

    fun stopListening() {
        stopListeningRequested = true
    }

    /** 음성 샘플 → 글자. sampleRate 가 16k 가 아니면 sherpa 가 알아서 변환. */
    suspend fun transcribe(samples: FloatArray, sampleRate: Int = STT_SAMPLE_RATE): String =
        withContext(Dispatchers.Default) {
            val r = recognizer ?: return@withContext ""
            sttLock.withLock {
                val t0 = System.currentTimeMillis()
                val stream = r.createStream()
                try {
                    stream.acceptWaveform(samples, sampleRate)
                    r.decode(stream)
                    val text = r.getResult(stream).text.trim()
                    Log.d(TAG, "STT ${System.currentTimeMillis() - t0}ms: $text")
                    text
                } finally {
                    stream.release()
                }
            }
        }

    // ------------------------------------------------------------ TTS
    /** 문장 단위로 생성하면서 바로 재생 (첫 소리까지 지연을 줄이려고, 강의 p.24). 끝나면 반환. */
    suspend fun speak(text: String, speed: Float = 1.0f) = withContext(Dispatchers.Default) {
        val engine = tts ?: return@withContext
        val sentences = splitSentences(text)
        if (sentences.isEmpty()) return@withContext
        stopSpeakingRequested = false

        ttsLock.withLock {
            val sampleRate = engine.sampleRate()
            val track = newAudioTrack(sampleRate)
            audioTrack = track
            track.play()
            val audioChannel = Channel<FloatArray>(capacity = 2)
            try {
                coroutineScope {
                    // 생성 담당: 다음 문장을 미리 만들어 둠
                    launch {
                        try {
                            val t0 = System.currentTimeMillis()
                            for ((i, s) in sentences.withIndex()) {
                                if (stopSpeakingRequested) break
                                val audio = engine.generate(text = s, sid = 0, speed = speed)
                                if (i == 0) Log.d(TAG, "TTS 첫 문장 ${System.currentTimeMillis() - t0}ms: $s")
                                audioChannel.send(audio.samples)
                            }
                        } finally {
                            audioChannel.close()
                        }
                    }
                    // 재생 담당
                    withContext(Dispatchers.IO) {
                        val pause = FloatArray(sampleRate * 15 / 100) // 문장 사이 쉼
                        for (samples in audioChannel) {
                            if (!writeChunked(track, samples) || !writeChunked(track, pause)) break
                        }
                    }
                }
            } finally {
                audioChannel.cancel()
                runCatching { track.stop() }
                track.release()
                audioTrack = null
            }
        }
    }

    fun stopSpeaking() {
        stopSpeakingRequested = true
        runCatching { audioTrack?.pause(); audioTrack?.flush() }
    }

    // ------------------------------------------------------------ 유틸
    // 잘게 나눠 쓰면서 중단 요청을 확인 (멈춤 버튼이 바로 먹히게)
    private fun writeChunked(track: AudioTrack, samples: FloatArray): Boolean {
        var off = 0
        while (off < samples.size) {
            if (stopSpeakingRequested) return false
            val n = minOf(1024, samples.size - off)
            val w = track.write(samples, off, n, AudioTrack.WRITE_BLOCKING)
            if (w < 0) return false
            off += w
        }
        return true
    }

    fun splitSentences(text: String): List<String> =
        text.split(Regex("(?<=[.!?。？！])\\s+|\\n+"))
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    private fun newAudioTrack(sampleRate: Int): AudioTrack {
        val minBuf = AudioTrack.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_FLOAT
        )
        return AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANT)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(minBuf * 2)
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
    }

    // espeak-ng-data 는 C 코드가 파일로 읽어서 assets → 내부 저장소로 복사 (처음 한 번)
    private fun copyAssetDir(am: AssetManager, path: String, root: File): String {
        val target = File(root, path)
        val marker = File(target, ".copied")
        if (!marker.exists()) {
            copyRecursive(am, path, root)
            marker.writeText("ok")
        }
        return target.absolutePath
    }

    private fun copyRecursive(am: AssetManager, path: String, root: File) {
        val children = am.list(path).orEmpty()
        if (children.isEmpty()) {
            val out = File(root, path)
            out.parentFile?.mkdirs()
            am.open(path).use { input -> out.outputStream().use { input.copyTo(it) } }
        } else {
            File(root, path).mkdirs()
            children.forEach { copyRecursive(am, "$path/$it", root) }
        }
    }

    // 디버그 빌드: TTS 로 만든 소리를 다시 STT 로 돌려 두 모델이 기기에서 동작하는지 로그로 확인
    private suspend fun selfTest() {
        val engine = tts ?: return
        val text = "다음 배송지는 어디야"
        val t0 = System.currentTimeMillis()
        val audio = ttsLock.withLock { engine.generate(text = text, sid = 0, speed = 1.0f) }
        val ttsMs = System.currentTimeMillis() - t0
        val heard = transcribe(audio.samples, audio.sampleRate)
        Log.d(TAG, "SELFTEST tts=${ttsMs}ms (${audio.samples.size / audio.sampleRate.toFloat()}s) 입력='$text' STT='$heard'")
    }
}

package com.example.logion.chat

import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.logion.data.remote.ChatRequest
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.data.remote.TtsRequest
import com.example.logion.speech.AudioPlayer
import com.example.logion.speech.VoiceRecorder
import com.example.logion.speech.pcmToWav
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import okhttp3.MediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

// ==============================
// AI 채팅 + 음성 대화 상태
// AI 채팅 탭과 아래 음성 버튼(VoiceDock)이 같이 씀
//   🎤 녹음(16kHz wav) → 보드 POST /api/assistant/voice (STT → AI → TTS)
//      → 알아들은 말·답 말풍선 → 응답 음성(audio_url) 재생
//   글자 입력 → POST /api/assistant/chat → 답 말풍선 (+ 소리 켜짐이면 POST /api/assistant/tts 로 읽기)
// 폰에는 STT·TTS 모델이 없음. 화면·마이크·스피커만 씀 (docs/voice_api.md)
// ==============================

data class ChatMessage(
    val text: String,
    val isUser: Boolean,
    val options: List<String> = emptyList(), // 되묻기 선택지
    val viaVoice: Boolean = false,
)

enum class VoiceState { Idle, Listening, Thinking, Speaking }

class ChatController(
    private val scope: CoroutineScope,
    private val onRouteChanged: () -> Unit,
    private val onOpenScanner: () -> Unit,
) {
    // 되묻기 상태(예: "어떤 삼각김밥인가요?", "납품 완료할까요?")는 보드가 session_id 별로 기억함
    private val sessionId = "app-" + UUID.randomUUID().toString().take(8)

    val messages = mutableStateListOf(
        ChatMessage("배송 업무를 말하거나 입력해 보세요. 🎤 버튼을 누르고 말하면 보드가 알아듣고 답을 읽어 드려요.", isUser = false)
    )

    var isSending by mutableStateOf(false)
        private set

    // null: 확인 중 / true: 모델 준비됨 / false: 모델 없음 또는 보드 연결 실패
    var assistantReady by mutableStateOf<Boolean?>(null)
        private set
    // 보드 STT·TTS 준비됨 → 🎤 버튼을 켬
    var voiceReady by mutableStateOf<Boolean?>(null)
        private set
    var statusText by mutableStateOf("보드 연결 확인 중")
        private set

    var voiceState by mutableStateOf(VoiceState.Idle)
        private set
    var lastHeard by mutableStateOf<String?>(null)    // 마지막으로 알아들은 말
        private set
    var lastReply by mutableStateOf<String?>(null)    // 마지막 답
        private set
    var micLevel by mutableStateOf(0f)                // 0~1, 녹음 중 입력 크기
        private set

    var speakReplies by mutableStateOf(true)          // 답을 소리로 읽을지

    private val recorder = VoiceRecorder()
    private var voiceJob: Job? = null

    suspend fun refreshStatus() {
        try {
            val status = RetrofitClient.api.getAssistantStatus()
            assistantReady = status.ready
            voiceReady = status.ready && status.voiceReady == true
            statusText = when {
                !status.ready -> "AI 모델이 보드에 올라가 있지 않습니다"
                status.voiceReady != true -> "AI 연결됨 · 음성(STT·TTS) 꺼짐: ${status.voiceError ?: "보드 확인"}"
                else -> "AI 연결됨 · ${status.device ?: "보드"} · 음성 보드 처리"
            }
        } catch (e: Exception) {
            assistantReady = false
            voiceReady = false
            statusText = "보드에 연결할 수 없습니다 (${RetrofitClient.baseUrl}) · 더보기에서 주소 확인"
            Log.e(TAG, "AI 상태 조회 실패", e)
        }
    }

    /** 보드가 꺼졌다 켜져도 상태 카드가 따라가도록 주기적으로 확인 (연결 안 됨: 5초, 연결됨: 30초) */
    suspend fun keepStatusFresh() {
        while (true) {
            refreshStatus()
            delay(if (assistantReady == true) 30_000 else 5_000)
        }
    }

    // ------------------------------------------------------------ 글자로 보내기
    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank() || isSending || voiceState == VoiceState.Listening) return
        AudioPlayer.stop()
        scope.launch { ask(trimmed) }
    }

    /** 글자로 묻고 답을 말풍선에 추가. 소리 켜짐이면 보드 TTS 로 읽어 줌 */
    private suspend fun ask(text: String) {
        messages.add(ChatMessage(text, isUser = true))
        isSending = true
        val spoken = try {
            val r = RetrofitClient.api.chat(ChatRequest(text = text, sessionId = sessionId))
            messages.add(ChatMessage(r.reply, isUser = false, options = r.options.orEmpty()))
            Log.d(TAG, "AI 응답: fn=${r.fn} route=${r.route} action=${r.action} ${r.latencyMs}ms")
            handleAction(r.action)
            lastReply = r.reply
            r.reply
        } catch (e: Exception) {
            Log.e(TAG, "AI 채팅 실패", e)
            showError(e)
            null
        } finally {
            isSending = false
        }
        if (spoken != null && speakReplies && voiceReady == true) {
            try {
                voiceState = VoiceState.Speaking
                val t = RetrofitClient.api.tts(TtsRequest(spoken))
                AudioPlayer.play(RetrofitClient.fullUrl(t.audioUrl))
            } catch (e: Exception) {
                Log.e(TAG, "보드 TTS 실패", e)   // 글자는 이미 보였으니 소리만 건너뜀
            } finally {
                voiceState = VoiceState.Idle
            }
        }
    }

    // ------------------------------------------------------------ 음성으로 묻기
    /** 🎤 버튼: 대기→녹음 시작 / 녹음 중→여기까지 녹음해 보냄 / 읽는 중→읽기 중단 */
    fun onMicPressed() {
        when (voiceState) {
            VoiceState.Listening -> recorder.stop()
            VoiceState.Speaking -> AudioPlayer.stop()
            VoiceState.Idle -> startVoice()
            VoiceState.Thinking -> Unit // 보드 응답 대기 중에는 무시
        }
    }

    fun stopSpeaking() = AudioPlayer.stop()

    private fun startVoice() {
        if (voiceReady != true || isSending) return
        voiceJob = scope.launch {
            try {
                lastHeard = null
                voiceState = VoiceState.Listening
                val pcm = recorder.record(onLevel = { micLevel = it })
                micLevel = 0f
                if (pcm == null) {
                    lastHeard = "(마이크를 열 수 없어요)"
                    return@launch
                }

                voiceState = VoiceState.Thinking
                isSending = true
                val wav = pcmToWav(pcm)
                val part = MultipartBody.Part.createFormData(
                    "file", "voice.wav", RequestBody.create(MediaType.parse("audio/wav"), wav)
                )
                val sid = RequestBody.create(MediaType.parse("text/plain"), sessionId)
                val r = try {
                    RetrofitClient.api.voice(part, sid)
                } catch (e: Exception) {
                    Log.e(TAG, "음성 업로드 실패", e)
                    lastHeard = "(보드 응답 없음)"
                    showError(e)
                    return@launch
                } finally {
                    isSending = false
                }
                Log.d(TAG, "보드 음성: \"${r.text}\" fn=${r.fn} route=${r.route} ${r.latency}")

                val heard = cleanStt(r.text.orEmpty())
                lastHeard = heard.ifBlank { "(못 알아들었어요)" }
                if (heard.isNotBlank()) messages.add(ChatMessage(heard, isUser = true, viaVoice = true))
                messages.add(ChatMessage(r.reply, isUser = false, options = r.options.orEmpty()))
                lastReply = r.reply
                handleAction(r.action)

                val audio = r.audioUrl
                if (speakReplies && audio != null) {
                    voiceState = VoiceState.Speaking
                    AudioPlayer.play(RetrofitClient.fullUrl(audio))
                }
            } catch (e: Exception) {
                Log.e(TAG, "음성 처리 실패", e)
                lastHeard = "(음성 처리 실패: ${e.message})"
            } finally {
                micLevel = 0f
                isSending = false
                voiceState = VoiceState.Idle
            }
        }
    }

    private fun handleAction(action: String?) {
        when (action) {
            "refresh_route", "refresh_stop" -> onRouteChanged()
            "open_scanner" -> onOpenScanner()
        }
    }

    private suspend fun showError(e: Exception) {
        val msg = when (e) {
            is IOException -> "보드에 연결할 수 없습니다. 더보기에서 보드 주소를 확인해 주세요."
            is HttpException -> when (e.code()) {
                503 -> "AI 모델이 보드에 올라가 있지 않습니다."
                415 -> "녹음 파일 형식을 확인해 주세요."
                413 -> "녹음이 너무 깁니다."
                422 -> "입력한 내용을 다시 확인해 주세요."
                else -> "보드에 문제가 발생했습니다. (${e.code()})"
            }
            else -> "응답을 받지 못했습니다."
        }
        messages.add(ChatMessage(msg, isUser = false))
        lastReply = msg
        refreshStatus() // 실패하면 상태 카드도 바로 갱신
    }

    // SenseVoice 는 문장 끝에 마침표를 붙임 → 말풍선에는 말한 글자만
    private fun cleanStt(text: String) = text.trim().trimEnd('.', '。', '?', '!', ',').trim()

    private companion object {
        const val TAG = "API_CHAT"
    }
}

package com.example.logion.chat

import android.util.Log
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.logion.data.remote.ChatRequest
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.speech.SpeechEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

// ==============================
// AI 채팅 + 음성 대화 상태
// AI 채팅 탭과 아래 음성 버튼(VoiceDock)이 같이 씀
//   🎤 듣기(VAD) → STT → POST /api/assistant/chat → 답 표시 + TTS 로 읽기
// ==============================

data class ChatMessage(
    val text: String,
    val isUser: Boolean,
    val options: List<String> = emptyList(), // 되묻기 선택지
    val viaVoice: Boolean = false,
)

enum class VoiceState { Idle, Listening, Recognizing, Thinking, Speaking }

class ChatController(
    private val scope: CoroutineScope,
    private val onRouteChanged: () -> Unit,
    private val onOpenScanner: () -> Unit,
) {
    // 되묻기 상태는 서버가 session_id 별로 기억함
    private val sessionId = "app-" + UUID.randomUUID().toString().take(8)

    val messages = mutableStateListOf(
        ChatMessage("배송 업무를 말하거나 입력해 보세요. 🎤 버튼을 누르고 말하면 답을 읽어 드려요.", isUser = false)
    )

    var isSending by mutableStateOf(false)
        private set

    // null: 확인 중 / true: 모델 준비됨 / false: 모델 없음 또는 서버 연결 실패
    var assistantReady by mutableStateOf<Boolean?>(null)
        private set
    var statusText by mutableStateOf("AI 모델 상태 확인 중")
        private set

    var voiceState by mutableStateOf(VoiceState.Idle)
        private set
    var lastHeard by mutableStateOf<String?>(null)    // 마지막으로 알아들은 말
        private set
    var lastReply by mutableStateOf<String?>(null)    // 마지막 답
        private set
    var micLevel by mutableStateOf(0f)                // 0~1, 듣는 중 입력 크기
        private set

    var speakReplies by mutableStateOf(true)          // 답을 소리로 읽을지

    private var voiceJob: Job? = null

    suspend fun refreshStatus() {
        try {
            val status = RetrofitClient.api.getAssistantStatus()
            assistantReady = status.ready
            statusText = if (status.ready) "AI 연결됨 · ${status.device ?: "서버"}"
            else "AI 모델이 서버에 올라가 있지 않습니다"
        } catch (e: Exception) {
            assistantReady = false
            statusText = "서버에 연결할 수 없습니다"
            Log.e(TAG, "AI 상태 조회 실패", e)
        }
    }

    /** 서버가 꺼졌다 켜져도 상태 카드가 따라가도록 주기적으로 확인 (연결 안 됨: 5초, 연결됨: 30초) */
    suspend fun keepStatusFresh() {
        while (true) {
            refreshStatus()
            delay(if (assistantReady == true) 30_000 else 5_000)
        }
    }

    // ------------------------------------------------------------ 글자로 보내기
    fun send(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank() || isSending) return
        scope.launch { ask(trimmed, viaVoice = false) }
    }

    /** 서버에 묻고 답을 말풍선에 추가. 답 문장을 돌려줌. */
    private suspend fun ask(text: String, viaVoice: Boolean): String {
        messages.add(ChatMessage(text, isUser = true, viaVoice = viaVoice))
        isSending = true
        val reply = try {
            val r = RetrofitClient.api.chat(ChatRequest(text = text, sessionId = sessionId))
            messages.add(ChatMessage(r.reply, isUser = false, options = r.options.orEmpty()))
            Log.d(TAG, "AI 응답: fn=${r.fn} action=${r.action} ${r.latencyMs}ms")
            when (r.action) {
                "refresh_route", "refresh_stop" -> onRouteChanged()
                "open_scanner" -> onOpenScanner()
            }
            // 되묻기 선택지가 있으면 같이 읽어 줌
            if (r.options.isNullOrEmpty()) r.reply
            else r.reply + " " + r.options.joinToString(", ") + "."
        } catch (e: Exception) {
            Log.e(TAG, "AI 채팅 실패", e)
            val msg = when (e) {
                is IOException -> "서버에 연결할 수 없습니다."
                is HttpException -> when (e.code()) {
                    503 -> "AI 모델이 서버에 올라가 있지 않습니다."
                    422 -> "입력한 내용을 다시 확인해 주세요."
                    else -> "서버에 문제가 발생했습니다."
                }
                else -> "응답을 받지 못했습니다."
            }
            messages.add(ChatMessage(msg, isUser = false))
            refreshStatus() // 실패하면 상태 카드도 바로 갱신
            msg
        } finally {
            isSending = false
        }
        lastReply = reply
        if (speakReplies && SpeechEngine.isReady) {
            voiceState = VoiceState.Speaking
            runCatching { SpeechEngine.speak(reply) }.onFailure { Log.e(TAG, "TTS 실패", it) }
        }
        voiceState = VoiceState.Idle
        return reply
    }

    // ------------------------------------------------------------ 음성으로 묻기
    /** 🎤 버튼: 대기→듣기 시작 / 듣는 중→여기까지 듣고 인식 / 말하는 중→읽기 중단 */
    fun onMicPressed() {
        when (voiceState) {
            VoiceState.Listening -> SpeechEngine.stopListening()
            VoiceState.Speaking -> SpeechEngine.stopSpeaking()
            VoiceState.Idle -> startVoice()
            else -> Unit // 인식·응답 대기 중에는 무시
        }
    }

    private fun startVoice() {
        if (!SpeechEngine.isReady || isSending) return
        voiceJob = scope.launch {
            try {
                lastHeard = null
                voiceState = VoiceState.Listening
                val samples = SpeechEngine.listen(onLevel = { micLevel = (it * 4f).coerceAtMost(1f) })
                micLevel = 0f

                voiceState = VoiceState.Recognizing
                val heard = samples?.let { cleanStt(SpeechEngine.transcribe(it)) }.orEmpty()
                if (heard.isBlank()) {
                    lastHeard = "(못 알아들었어요)"
                    if (speakReplies) {
                        voiceState = VoiceState.Speaking
                        SpeechEngine.speak("잘 못 들었어요. 다시 말씀해 주세요.")
                    }
                    return@launch
                }
                lastHeard = heard
                voiceState = VoiceState.Thinking
                ask(heard, viaVoice = true)
            } catch (e: Exception) {
                Log.e(TAG, "음성 처리 실패", e)
                lastHeard = "(음성 처리 실패: ${e.message})"
            } finally {
                micLevel = 0f
                voiceState = VoiceState.Idle
            }
        }
    }

    // SenseVoice 는 문장 끝에 마침표를 붙임 → 서버에는 말한 글자만 보냄
    private fun cleanStt(text: String) = text.trim().trimEnd('.', '。', '?', '!', ',').trim()

    private companion object {
        const val TAG = "API_CHAT"
    }
}

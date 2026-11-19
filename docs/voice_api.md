# 음성 API (보드에서 STT·TTS) — 앱 담당용

폰은 **화면·마이크·스피커만** 맡는다. 녹음한 wav 를 보드에 올리면 보드가 아래를 모두 하고 결과를 돌려준다.

- STT: SenseVoice, CPU
- 파이프라인: LLM 은 NPU, 값 보정과 DB 기록 포함
- TTS: VITS, CPU

앱 안의 sherpa-onnx STT·TTS 는 더 이상 쓰지 않는다.

```
 폰  🎤 녹음 (16kHz mono wav) ──POST /api/assistant/voice──▶  보드: VAD → STT → 파이프라인(/chat 과 같음) → TTS
     화면: text·reply 표시   ◀────────── JSON ────────────
     🔊 재생                 ◀──GET audio_url (wav)────────
```

보드 실측: 5문장 모두 성공. 서버 처리는 1.3~3.5초다 (STT 0.2~0.35초 + LLM 0.5~1.9초 + TTS 0.6~1.2초). 자세한 결과는 [results/board_voice/report.md](../results/board_voice/report.md) 에 있다.

## 1. `POST /api/assistant/voice`

`multipart/form-data` 로 보낸다.

| 필드 | 필수 | 설명 |
|---|---|---|
| `file` | O | 녹음 파일. **wav 16kHz mono 16bit 권장**. 다른 샘플레이트나 스테레오 wav 는 보드가 16kHz mono 로 바꾼다. wav/flac/ogg 는 되고 m4a/mp3 는 안 된다(415). 5MB·15초까지 |
| `session_id` | | 기본 `"default"`. 되묻기(예: "어떤 삼각김밥인가요?") 상태를 이어 가는 키다. 앱 실행마다 하나 만들어 계속 쓴다 (지금 `ChatController.sessionId` 그대로) |

녹음 앞뒤의 무음은 보드가 VAD 로 잘라 낸다. 버튼을 늦게 떼도 괜찮다.

### curl

```bash
curl -s -F file=@다음어디야.wav -F session_id=demo http://<보드 IP>:8000/api/assistant/voice
curl -s -o reply.wav http://<보드 IP>:8000/api/assistant/voice/audio/<id>      # 응답 음성
```

### 응답 (200) — 보드 실측 예

```json
{
  "text": "우유 두 개 터졌어.",
  "reply": "GS25 성수연무장점 서울우유 2개 파손으로 기록했어요.",
  "fn": "report_issue",
  "call": {"item": "서울우유", "qty": 2, "unit": "개", "product_id": 1, "type": "파손"},
  "route": "llm",
  "ask": null,
  "options": null,
  "action": "refresh_stop",
  "stop_id": 4,
  "conf": 0.0,
  "latency": {"stt": 191, "llm": 1940, "tts": 919, "total": 3053},
  "audio_url": "/api/assistant/voice/audio/434005919ee04e0ba7772514e0ae12cc",
  "input": {"sample_rate": 16000, "seconds": 2.94}
}
```

| 필드 | 뜻 / 앱이 할 일 |
|---|---|
| `text` | 보드가 알아들은 말 (STT 오인식 별칭 `config/stt_aliases.json` 으로 고친 뒤. 예: "정자님" → "점장님"). 사용자 말풍선에 표시한다. 끝의 `.`·`?` 는 지워도 된다 |
| `stt_text` | STT 가 낸 그대로의 글자 (확인용) |
| `reply` | 답 문장. AI 말풍선에 표시한다 |
| `fn`, `call`, `route`, `ask`, `options`, `action`, `stop_id`, `conf` | `/api/assistant/chat` 응답과 같다. `options` 가 있으면 선택지 버튼을 만들고, `action` 이 `refresh_route`·`refresh_stop` 이면 목록을 새로 고친다. `open_scanner` 면 스캔 화면을 연다 (지금 코드 그대로) |
| `latency` | ms. `llm` 은 파이프라인 전체(LLM + 값 보정 + DB)다. 로그용 |
| `audio_url` | 응답 음성 wav (22.05kHz mono). **`BASE_URL` 뒤에 붙여** 재생한다. 10분 또는 최근 32개까지 보관 |
| `input` | 올린 파일의 원래 샘플레이트와 길이(초). 확인용 |

**못 알아들었을 때:** 말이 없거나 STT 결과가 비면 LLM 을 부르지 않고 아래처럼 돌려준다. 이 답도 `audio_url` 로 읽어 준다.

```json
{"text": "", "reply": "잘 못 들었어요. 다시 말씀해 주세요.", "fn": null, "action": null, "route": "not_heard", ...}
```

**오류:**

| 코드 | 상황 | 앱 표시 예 |
|---|---|---|
| 503 | LLM 이나 STT/TTS 가 보드에 안 올라감 (`detail` 에 이유) | "AI 모델이 서버에 올라가 있지 않습니다." |
| 415 | 읽을 수 없는 음성 형식 | "녹음 파일 형식을 확인해 주세요." |
| 413 | 5MB 초과 | — |
| 422 | `file` 이 없거나 비어 있음 | — |

### 응답 음성: 왜 `audio_url` 인가 (base64 대신)

- **`MediaPlayer` 가 URL 을 바로 재생한다.** `setDataSource(BASE_URL + audioUrl)` 두 줄이면 끝이다. 파일 저장이나 디코딩 코드가 필요 없다.
- **JSON 이 작다.** 응답 wav 는 120~260KB 인데 base64 로 넣으면 JSON 이 160~350KB 가 된다. Gson 파싱과 로그(OkHttp 로깅)가 무거워진다.
- **글자를 먼저 띄울 수 있다.** JSON 을 받자마자 말풍선을 띄우고, 소리는 이어서 받는다.
- **비용:** 요청이 하나 늘지만 같은 망에서 10~25ms 였다 (실측).

**납품 완료는 한 번 되묻는다 (2026-11-20):** `complete` 는 바로 기록하지 않고 `route: "confirm_ask"`, `reply: "GS25 성수연무장점 납품 완료할까요?"`, `options: ["네", "아니요"]` 로 돌려준다.
같은 `session_id` 로 다음 말이 "응/네/어/맞아 …" 면 `route: "confirm_yes"` 로 기록하고 `action: "refresh_stop"`, "아니 …" 면 `route: "confirm_no"` (기록 안 함). 다른 말이면 되묻기를 버리고 그 말을 새로 처리한다. 한 음절 "네" 는 짧아 놓칠 수 있어 "네 맞아요" 처럼 말하는 것이 안전하다.

### `POST /api/assistant/tts` (글자 답을 소리로)

글자로 물었을 때(`/chat`) 답을 읽어 주려고 쓴다. `{"text": "다음은 GS25 성수연무장점이에요."}` → `{"text": …, "audio_url": "/api/assistant/voice/audio/…", "latency": {"tts": 650}}`. 음성은 `/voice` 와 같이 `audio_url` 로 받는다. TTS 가 없으면 503.

## 2. `GET /api/assistant/status` (필드 추가)

```json
{"ready": true, "device": "RK3588 NPU (rkllm, ...)", "error": null, "voice_ready": true, "voice_error": null}
```

`voice_ready` 가 true 일 때만 🎤 버튼을 켠다. 지금은 앱의 `SpeechEngine.isReady` 를 보고 켠다.

## 3. 앱에서 바꿀 것 — 2026-11-20 모두 반영함

아래 7가지를 그대로 반영했다: `RetrofitClient.kt`(주소는 더보기 화면에서 저장, 제한 시간 20초), `LogiOnApi.kt`(`voice()`·`tts()`), `speech/VoiceRecorder.kt`·`Wav.kt`(녹음, 말 끝 1초 자동 종료), `speech/AudioPlayer.kt`(재생), `chat/ChatController.kt`, `LogiOnApp.kt`, sherpa AAR·모델 제거(debug APK 430MB → 58MB). 5번은 바꿔서, 글자 입력의 답도 소리 켜짐이면 `POST /api/assistant/tts` 로 읽는다. 아래 표는 처음 쓴 요청 그대로 둔다.

| # | 파일 | 바꿀 내용 | 이유 |
|---|---|---|---|
| 1 | `data/remote/RetrofitClient.kt` | `BASE_URL` 을 보드 주소로 (`http://<보드 IP>:8000/`). OkHttp `readTimeout` 을 20초로 | STT+LLM+TTS 가 최대 3.5초쯤이고, LLM 제한 시간이 8초다. 기본 10초는 빠듯하다 |
| 2 | `data/remote/LogiOnApi.kt` | 아래 `voice()` 와 `VoiceResponse` 추가. `AssistantStatusResponse` 에 `voiceReady` 추가 | 새 API |
| 3 | 새 파일 `speech/VoiceRecorder.kt` (또는 `SpeechEngine` 정리) | `AudioRecord` 16kHz mono PCM16 으로 녹음 → wav 헤더(44바이트) 붙여 `ByteArray`. 멈춤 조건: 🎤 다시 누름 / 10초 / (선택) 소리 크기가 말 뒤 1초 이상 작으면 | 폰은 녹음만. 지금 `SpeechEngine.listen()` 의 `AudioRecord` 부분을 그대로 쓰면 된다. sherpa VAD 대신 크기 기준이면 충분하다 (앞뒤 무음은 보드가 자름) |
| 4 | `chat/ChatController.kt` `startVoice()` | `listen()`→`transcribe()`→`ask()` 를 **녹음 → `api.voice()` → 말풍선 2개(`text`, `reply`) → `action` 처리 → `audio_url` 재생** 으로 바꿈. 상태는 Listening → Thinking → Speaking | STT·TTS 가 보드로 감 |
| 5 | `chat/ChatController.kt` `ask()` (글자 입력) | `/chat` 그대로 쓴다. 답을 소리로 읽던 `SpeechEngine.speak()` 는 뺀다 (글자로만) | 글자 입력은 TTS 없음. 소리도 필요하면 보드에 TTS 전용 API 를 추가할 수 있다 (말해 주면 추가) |
| 6 | `LogiOnApp.kt` | `SpeechEngine.init(context)` 와 `speechReady` 를 빼고, 🎤 활성화를 `status.voiceReady` 로 | 앱 시작 때 모델 로딩(수 초·수백 MB 메모리)이 없어진다 |
| 7 | (정리, 선택) `app/build.gradle*`, `assets/` | sherpa-onnx AAR(48MB) 과 assets 의 VAD·STT·TTS 모델(306MB)을 빼면 지금 410MB 인 debug APK 가 크게 줄어든다 | 폰에서 안 씀. 되돌릴 일이 있으면 #6 까지만 하고 나중에 |

`RECORD_AUDIO` 권한 요청은 지금 그대로 둔다. HTTP(평문) 접속도 지금 `10.0.2.2` 로 되고 있으니 설정 그대로 보드 IP 에 된다.

### 코드 예 (Kotlin)

```kotlin
// LogiOnApi.kt
data class VoiceLatency(val stt: Int, val llm: Int, val tts: Int, val total: Int)
data class VoiceResponse(
    val text: String,
    val reply: String,
    val fn: String?,
    val route: String?,
    val ask: String?,
    val options: List<String>?,
    val action: String?,
    @SerializedName("stop_id") val stopId: Int?,
    val latency: VoiceLatency,
    @SerializedName("audio_url") val audioUrl: String?,
)

@Multipart
@POST("api/assistant/voice")
suspend fun voice(
    @Part file: MultipartBody.Part,
    @Part("session_id") sessionId: RequestBody,
): VoiceResponse
```

```kotlin
// 녹음 결과(16kHz mono PCM16 ShortArray) → wav → 업로드
fun pcmToWav(pcm: ShortArray, sr: Int = 16000): ByteArray {
    val data = ByteBuffer.allocate(pcm.size * 2).order(ByteOrder.LITTLE_ENDIAN).apply { pcm.forEach { putShort(it) } }.array()
    val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
    h.put("RIFF".toByteArray()).putInt(36 + data.size).put("WAVE".toByteArray())
    h.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(1).putInt(sr).putInt(sr * 2).putShort(2).putShort(16)
    h.put("data".toByteArray()).putInt(data.size)
    return h.array() + data
}

val wav = pcmToWav(recorded)
val part = MultipartBody.Part.createFormData("file", "voice.wav", wav.toRequestBody("audio/wav".toMediaType()))
val r = RetrofitClient.api.voice(part, sessionId.toRequestBody("text/plain".toMediaType()))
messages.add(ChatMessage(r.text.ifBlank { "(못 알아들었어요)" }, isUser = true, viaVoice = true))
messages.add(ChatMessage(r.reply, isUser = false, options = r.options.orEmpty()))
when (r.action) { "refresh_route", "refresh_stop" -> onRouteChanged(); "open_scanner" -> onOpenScanner() }
```

```kotlin
// 응답 음성 재생 (끝날 때까지 기다림, 🎤 다시 누르면 stop())
suspend fun playUrl(url: String) = suspendCancellableCoroutine<Unit> { cont ->
    val mp = MediaPlayer().apply {
        setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
        setDataSource(RetrofitClient.BASE_URL.trimEnd('/') + url)
        setOnPreparedListener { it.start() }
        setOnCompletionListener { it.release(); if (cont.isActive) cont.resume(Unit) {} }
        setOnErrorListener { p, _, _ -> p.release(); if (cont.isActive) cont.resume(Unit) {}; true }
        prepareAsync()
    }
    cont.invokeOnCancellation { runCatching { mp.stop(); mp.release() } }
}
```

`RetrofitClient.BASE_URL` 은 지금 `private const` 다. 재생에 쓰려면 `const val` 로 공개하거나 `audioUrl` 을 받는 쪽에 주소를 넘긴다.

## 4. 확인 순서 (앱 고친 뒤)

1. 보드에서 `curl -s localhost:8000/api/assistant/status` 를 실행해 `"voice_ready": true` 인지 본다.
2. 앱 AI 채팅 탭에서 🎤 → "다음 어디야".
   - 말풍선: "다음 어디야" / "다음은 GS25 성수연무장점이에요. …"
   - 소리가 나오면 된다.
3. 보드 로그 `~/LogiOn/logs/backend.log` 에 `POST /api/assistant/voice 200` 과 `GET /api/assistant/voice/audio/... 200` 이 찍히는지 본다.

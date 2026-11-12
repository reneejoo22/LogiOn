package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.logion.chat.ChatController
import com.example.logion.chat.ChatMessage
import com.example.logion.chat.VoiceState
import com.example.logion.speech.SpeechEngine
import com.example.logion.speech.rememberMicAction
import com.example.logion.ui.theme.*

// ==============================
// AI 채팅 화면
// 백엔드 POST /api/assistant/chat 으로 AI 파이프라인과 대화
// 🎤: 온디바이스 STT(sherpa-onnx) → 서버 → 답을 TTS 로 읽음 (ChatController)
// ==============================

@Composable
fun ChatScreen(
    controller: ChatController,
    speechReady: Boolean,
) {
    var inputText by remember { mutableStateOf("") }
    val messages = controller.messages
    val isSending = controller.isSending
    val assistantReady = controller.assistantReady
    val statusText = controller.statusText
    val voiceState = controller.voiceState

    val listState = rememberLazyListState()
    val onMic = rememberMicAction { controller.onMicPressed() }

    // 화면을 열 때 AI 모델이 서버에 올라가 있는지 확인
    LaunchedEffect(Unit) {
        controller.refreshStatus()
    }

    fun sendMessage(text: String) {
        controller.send(text)
        inputText = ""
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.lastIndex)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(LogiOnBackground)
    ) {
        LogiOnTopBar()

        CompositionLocalProvider(
            LocalOverscrollFactory provides null,
            LocalRippleConfiguration provides null
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 18.dp, vertical = 14.dp)
            ) {
                // 화면 제목
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        modifier = Modifier.size(42.dp),
                        shape = RoundedCornerShape(12.dp),
                        color = LogiOnGreenLight
                    ) {
                        Box(
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.SmartToy,
                                contentDescription = null,
                                tint = LogiOnGreen2,
                                modifier = Modifier.size(23.dp)
                            )
                        }
                    }

                    Spacer(Modifier.width(10.dp))

                    Column {
                        Text(
                            text = "AI 채팅",
                            style = MaterialTheme.typography.headlineSmall,
                            color = LogiOnText
                        )

                        Text(
                            text = "말하거나 입력하면 AI 가 처리해요",
                            style = MaterialTheme.typography.bodySmall,
                            color = LogiOnSubText
                        )
                    }

                    Spacer(Modifier.weight(1f))

                    // 답을 소리로 읽을지
                    IconToggleButton(
                        checked = controller.speakReplies,
                        onCheckedChange = {
                            controller.speakReplies = it
                            if (!it) SpeechEngine.stopSpeaking()
                        }
                    ) {
                        Icon(
                            imageVector = if (controller.speakReplies) Icons.AutoMirrored.Filled.VolumeUp
                            else Icons.AutoMirrored.Filled.VolumeOff,
                            contentDescription = "답 읽어주기",
                            tint = if (controller.speakReplies) LogiOnGreen2 else LogiOnSubText
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                // AI 모델 연결 상태
                val isOff = assistantReady == false

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(13.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isOff) Color(0xFFFDECEC) else LogiOnGreenLight
                    ),
                    border = BorderStroke(
                        1.dp,
                        if (isOff) Color(0xFFF3C7C4) else Color(0xFFD0E6DB)
                    )
                ) {
                    Text(
                        text = statusText,
                        modifier = Modifier.padding(
                            horizontal = 12.dp,
                            vertical = 9.dp
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = if (isOff) Color(0xFFB3261E) else LogiOnGreen
                    )
                }

                Spacer(Modifier.height(10.dp))

                // 채팅 내용
                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    contentPadding = PaddingValues(vertical = 6.dp)
                ) {
                    items(messages) { message ->
                        ChatBubble(
                            message = message,
                            enabled = !isSending,
                            onOptionClick = { sendMessage(it) }
                        )
                    }
                }

                Spacer(Modifier.height(8.dp))

                // 메시지 입력 영역
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val listening = voiceState == VoiceState.Listening
                    FilledIconButton(
                        onClick = onMic,
                        enabled = speechReady && !isSending &&
                            voiceState != VoiceState.Recognizing && voiceState != VoiceState.Thinking,
                        modifier = Modifier.size(48.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = if (listening) LogiOnOrange else LogiOnGreenLight,
                            contentColor = if (listening) Color.White else LogiOnGreen2
                        )
                    ) {
                        Icon(
                            imageVector = when (voiceState) {
                                VoiceState.Listening -> Icons.Default.Stop
                                VoiceState.Speaking -> Icons.AutoMirrored.Filled.VolumeOff
                                else -> Icons.Default.Mic
                            },
                            contentDescription = "음성으로 말하기",
                            modifier = Modifier.size(20.dp)
                        )
                    }

                    Spacer(Modifier.width(8.dp))

                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = {
                            Text(
                                text = when (voiceState) {
                                    VoiceState.Listening -> "듣고 있어요…"
                                    VoiceState.Recognizing -> "알아듣는 중…"
                                    else -> "예: 다음 배송 어디야?"
                                },
                                style = MaterialTheme.typography.bodyMedium
                            )
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(15.dp)
                    )

                    Spacer(Modifier.width(8.dp))

                    FilledIconButton(
                        onClick = { sendMessage(inputText) },
                        enabled = inputText.isNotBlank() && !isSending,
                        modifier = Modifier.size(48.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = LogiOnGreen2,
                            contentColor = Color.White
                        )
                    ) {
                        if (isSending) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(18.dp),
                                strokeWidth = 2.dp,
                                color = Color.White
                            )
                        } else {
                            Icon(
                                imageVector = Icons.Default.Send,
                                contentDescription = "전송",
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }

                Spacer(Modifier.height(4.dp))

                Text(
                    text = "납품 완료·이상 보고는 실제 배송 기록에 반영됩니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )
            }
        }
    }
}

// 사용자 / AI 메시지 말풍선
@Composable
private fun ChatBubble(
    message: ChatMessage,
    enabled: Boolean,
    onOptionClick: (String) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (message.isUser) {
            Arrangement.End
        } else {
            Arrangement.Start
        }
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth(0.78f),
            shape = RoundedCornerShape(16.dp),
            color = if (message.isUser) LogiOnGreen2 else LogiOnCard,
            border = if (message.isUser) null
            else BorderStroke(1.dp, LogiOnBorder)
        ) {
            Column(
                modifier = Modifier.padding(
                    horizontal = 13.dp,
                    vertical = 10.dp
                )
            ) {
                Text(
                    text = if (message.viaVoice) "🎤 ${message.text}" else message.text,
                    style = MaterialTheme.typography.bodyMedium,
                    color = if (message.isUser) Color.White else LogiOnText
                )

                // 되묻기 선택지 버튼
                if (message.options.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        message.options.forEach { option ->
                            OutlinedButton(
                                onClick = { onOptionClick(option) },
                                enabled = enabled,
                                shape = RoundedCornerShape(999.dp),
                                border = BorderStroke(1.5.dp, LogiOnGreen2),
                                contentPadding = PaddingValues(
                                    horizontal = 12.dp,
                                    vertical = 4.dp
                                )
                            ) {
                                Text(
                                    text = option,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = LogiOnGreen2
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

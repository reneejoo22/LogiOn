package com.example.logion.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.automirrored.filled.VolumeOff
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.logion.chat.VoiceState
import com.example.logion.ui.theme.*

// ==============================
// 공통 음성 입력 영역
// 🎤 누르고 말하면 → 온디바이스 STT → AI 서버 → 답을 TTS 로 읽어 줌
// ==============================

@Composable
fun VoiceDock(
    voiceState: VoiceState,
    speechReady: Boolean,
    speechError: String?,
    lastHeard: String?,
    lastReply: String?,
    micLevel: Float,
    onVoiceClick: () -> Unit
) {
    val isListening = voiceState == VoiceState.Listening
    val isBusy = voiceState == VoiceState.Recognizing || voiceState == VoiceState.Thinking

    val title = when {
        speechError != null -> "음성 모델을 불러오지 못했어요"
        !speechReady -> "음성 모델 불러오는 중…"
        voiceState == VoiceState.Listening -> "듣고 있어요"
        voiceState == VoiceState.Recognizing -> "알아듣는 중…"
        voiceState == VoiceState.Thinking -> "“${lastHeard.orEmpty()}”"
        voiceState == VoiceState.Speaking -> lastReply ?: "말하는 중"
        lastHeard != null -> "“$lastHeard”"
        else -> "무엇을 도와드릴까요?"
    }
    val subtitle = when {
        speechError != null -> speechError
        !speechReady -> "처음 한 번은 몇 초 걸립니다"
        voiceState == VoiceState.Listening -> "말을 멈추면 자동으로 끝나요 · 버튼을 누르면 바로 끝"
        voiceState == VoiceState.Thinking -> "AI 가 처리하는 중…"
        voiceState == VoiceState.Speaking -> "버튼을 누르면 읽기를 멈춰요"
        lastReply != null -> lastReply
        else -> "버튼을 누르고 말해 보세요 (배송 완료, 이상 보고 등)"
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 5.dp),
        shape = RoundedCornerShape(18.dp),
        color = if (isListening) LogiOnOrangeLight else LogiOnCard,
        tonalElevation = 1.dp,
        shadowElevation = 2.dp
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 13.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // 음성 입력 시작, 종료 버튼
                FilledIconButton(
                    onClick = onVoiceClick,
                    enabled = speechReady && !isBusy,
                    modifier = Modifier.size(42.dp),
                    shape = CircleShape,
                    colors = IconButtonDefaults.filledIconButtonColors(
                        containerColor = if (isListening) LogiOnOrange else LogiOnGreen2,
                        contentColor = LogiOnCard
                    )
                ) {
                    when {
                        isBusy -> CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = LogiOnCard
                        )
                        else -> Icon(
                            imageVector = when {
                                !speechReady -> Icons.Default.MicOff
                                isListening -> Icons.Default.Stop
                                voiceState == VoiceState.Speaking -> Icons.AutoMirrored.Filled.VolumeOff
                                else -> Icons.Default.Mic
                            },
                            contentDescription = "음성 입력",
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.width(11.dp))

                // 현재 음성 입력 상태
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        color = LogiOnText,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )

                    Spacer(modifier = Modifier.height(1.dp))

                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = LogiOnSubText,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }

            // 듣는 중 입력 크기 표시
            if (isListening) {
                LinearProgressIndicator(
                    progress = { micLevel },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 14.dp)
                        .padding(bottom = 8.dp),
                    color = LogiOnOrange,
                    trackColor = LogiOnOrangeLight
                )
            }
        }
    }
}

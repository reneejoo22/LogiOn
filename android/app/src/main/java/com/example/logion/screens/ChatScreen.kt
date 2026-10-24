package com.example.logion.screens

import android.util.Log
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
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.logion.data.remote.ChatRequest
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.ui.theme.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException
import java.util.UUID

// ==============================
// AI 채팅 화면
// 백엔드 POST /api/assistant/chat 으로 AI 파이프라인과 대화
// ==============================

private data class ChatMessage(
    val text: String,
    val isUser: Boolean,
    // 되묻기 선택지 (누르면 그 글자를 그대로 다시 보냄)
    val options: List<String> = emptyList()
)

@Composable
fun ChatScreen(
    onRouteChanged: () -> Unit = {},
    onOpenScanner: () -> Unit = {}
) {
    var inputText by remember { mutableStateOf("") }
    var isSending by remember { mutableStateOf(false) }

    // null: 확인 중 / true: 모델 준비됨 / false: 모델 없음 또는 서버 연결 실패
    var assistantReady by remember { mutableStateOf<Boolean?>(null) }
    var statusText by remember { mutableStateOf("AI 모델 상태 확인 중") }

    // 되묻기 상태는 서버가 session_id 별로 기억함
    val sessionId = remember { "app-" + UUID.randomUUID().toString().take(8) }

    val messages = remember {
        mutableStateListOf(
            ChatMessage(
                text = "배송 업무를 텍스트로 입력할 수 있는 화면입니다.",
                isUser = false
            )
        )
    }

    val listState = rememberLazyListState()
    val coroutineScope = rememberCoroutineScope()

    // 화면을 열 때 AI 모델이 서버에 올라가 있는지 확인
    LaunchedEffect(Unit) {
        try {
            val status = RetrofitClient.api.getAssistantStatus()
            assistantReady = status.ready
            statusText = if (status.ready) {
                "AI 연결됨 · ${status.device ?: "서버"}"
            } else {
                "AI 모델이 서버에 올라가 있지 않습니다"
            }
        } catch (e: Exception) {
            assistantReady = false
            statusText = "서버에 연결할 수 없습니다"
            Log.e("API_CHAT", "AI 상태 조회 실패", e)
        }
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isBlank() || isSending) return

        messages.add(
            ChatMessage(
                text = trimmed,
                isUser = true
            )
        )

        inputText = ""
        isSending = true

        coroutineScope.launch {
            try {
                val response = RetrofitClient.api.chat(
                    ChatRequest(
                        text = trimmed,
                        sessionId = sessionId
                    )
                )

                messages.add(
                    ChatMessage(
                        text = response.reply,
                        isUser = false,
                        options = response.options.orEmpty()
                    )
                )

                Log.d(
                    "API_CHAT",
                    "AI 응답: fn=${response.fn} action=${response.action} ${response.latencyMs}ms"
                )

                // 실행 결과에 따라 앱 화면 갱신
                when (response.action) {
                    "refresh_route", "refresh_stop" -> onRouteChanged()
                    "open_scanner" -> onOpenScanner()
                }
            } catch (e: Exception) {
                Log.e("API_CHAT", "AI 채팅 실패", e)

                val errorText = when (e) {
                    is IOException -> "서버에 연결할 수 없습니다."
                    is HttpException -> when (e.code()) {
                        503 -> "AI 모델이 서버에 올라가 있지 않습니다."
                        422 -> "입력한 내용을 다시 확인해 주세요."
                        else -> "서버에 문제가 발생했습니다."
                    }
                    else -> "응답을 받지 못했습니다."
                }

                messages.add(
                    ChatMessage(
                        text = errorText,
                        isUser = false
                    )
                )
            } finally {
                isSending = false
            }
        }
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
                            text = "배송 업무를 텍스트로 입력",
                            style = MaterialTheme.typography.bodySmall,
                            color = LogiOnSubText
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
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = {
                            Text(
                                text = "예: 다음 배송 어디야?",
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
                    text = message.text,
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

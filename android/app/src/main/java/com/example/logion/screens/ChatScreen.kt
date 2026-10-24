package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
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
import com.example.logion.ui.theme.*

// ==============================
// AI 채팅 화면
// 현재는 UI 프로토타입이며 실제 AI 연동은 추후 진행
// ==============================

private data class ChatMessage(
    val text: String,
    val isUser: Boolean
)

@Composable
fun ChatScreen() {
    var inputText by remember { mutableStateOf("") }

    val messages = remember {
        mutableStateListOf(
            ChatMessage(
                text = "배송 업무를 텍스트로 입력할 수 있는 화면입니다.",
                isUser = false
            )
        )
    }

    val listState = rememberLazyListState()

    fun sendMessage() {
        val text = inputText.trim()
        if (text.isBlank()) return

        messages.add(
            ChatMessage(
                text = text,
                isUser = true
            )
        )

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
                            text = "배송 업무를 텍스트로 입력",
                            style = MaterialTheme.typography.bodySmall,
                            color = LogiOnSubText
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                // 현재 개발 상태 안내
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(13.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = LogiOnGreenLight
                    ),
                    border = BorderStroke(
                        1.dp,
                        Color(0xFFD0E6DB)
                    )
                ) {
                    Text(
                        text = "프로토타입 · AI 파이프라인 연동 전",
                        modifier = Modifier.padding(
                            horizontal = 12.dp,
                            vertical = 9.dp
                        ),
                        style = MaterialTheme.typography.bodySmall,
                        color = LogiOnGreen
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
                        ChatBubble(message)
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
                        onClick = { sendMessage() },
                        enabled = inputText.isNotBlank(),
                        modifier = Modifier.size(48.dp),
                        colors = IconButtonDefaults.filledIconButtonColors(
                            containerColor = LogiOnGreen2,
                            contentColor = Color.White
                        )
                    ) {
                        Icon(
                            imageVector = Icons.Default.Send,
                            contentDescription = "전송",
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                Spacer(Modifier.height(4.dp))

                Text(
                    text = "실제 AI 응답은 LLM 파이프라인 연동 후 제공됩니다.",
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
    message: ChatMessage
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
            Text(
                text = message.text,
                modifier = Modifier.padding(
                    horizontal = 13.dp,
                    vertical = 10.dp
                ),
                style = MaterialTheme.typography.bodyMedium,
                color = if (message.isUser) Color.White else LogiOnText
            )
        }
    }
}
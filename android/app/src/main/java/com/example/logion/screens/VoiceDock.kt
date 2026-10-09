package com.example.logion.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.logion.ui.theme.*

// ==============================
// 공통 음성 입력 영역
// 음성 입력 시작과 종료 상태를 보여줌
// ==============================

@Composable
fun VoiceDock(
    isListening: Boolean,
    onVoiceClick: () -> Unit
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 5.dp),
        shape = RoundedCornerShape(18.dp),
        color = if (isListening) LogiOnOrangeLight else LogiOnCard,
        tonalElevation = 1.dp,
        shadowElevation = 2.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 13.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 음성 입력 시작,종료 버튼
            FilledIconButton(
                onClick = onVoiceClick,
                modifier = Modifier.size(42.dp),
                shape = CircleShape,
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (isListening) LogiOnOrange else LogiOnGreen2,
                    contentColor = LogiOnCard
                )
            ) {
                Icon(
                    imageVector = if (isListening) Icons.Default.Stop else Icons.Default.Mic,
                    contentDescription = "음성 입력",
                    modifier = Modifier.size(20.dp)
                )
            }

            Spacer(modifier = Modifier.width(11.dp))

            // 현재 음성 입력 상태
            Column {
                Text(
                    text = if (isListening) "듣고 있어요" else "무엇을 도와드릴까요?",
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(modifier = Modifier.height(1.dp))

                Text(
                    text = if (isListening) {
                        "배송 완료, 이상 보고 등을 말해보세요"
                    } else {
                        "버튼을 눌러 음성으로 빠르게 처리"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )
            }
        }
    }
}
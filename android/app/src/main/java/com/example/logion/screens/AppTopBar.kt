package com.example.logion.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.LocalShipping
import androidx.compose.material.icons.filled.NotificationsNone
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.logion.ui.theme.*

// ==============================
// 공통 상단바
// LogiOn 로고와 도움말, 알림 버튼을 보여줌
// ==============================

@Composable
fun LogiOnTopBar() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 22.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 앱 로고
        Surface(
            modifier = Modifier.size(38.dp),
            shape = RoundedCornerShape(11.dp),
            color = LogiOnGreen2
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(
                    imageVector = Icons.Default.LocalShipping,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(21.dp)
                )
            }
        }

        Spacer(modifier = Modifier.width(9.dp))

        // 앱 이름
        Text(
            text = "LogiOn",
            style = MaterialTheme.typography.titleLarge,
            color = LogiOnText
        )

        Spacer(modifier = Modifier.width(7.dp))

        Text(
            text = "D R I V E R",
            style = MaterialTheme.typography.labelSmall,
            color = LogiOnSubText
        )

        Spacer(modifier = Modifier.weight(1f))

        // 도움말 버튼
        IconButton(
            onClick = {},
            modifier = Modifier.size(38.dp)
        ) {
            Icon(
                imageVector = Icons.Default.HelpOutline,
                contentDescription = "도움말",
                tint = LogiOnGreen,
                modifier = Modifier.size(21.dp)
            )
        }

        // 알림 버튼
        Box {
            IconButton(
                onClick = {},
                modifier = Modifier.size(38.dp)
            ) {
                Icon(
                    imageVector = Icons.Default.NotificationsNone,
                    contentDescription = "알림",
                    tint = LogiOnGreen,
                    modifier = Modifier.size(21.dp)
                )
            }
        }
    }

    HorizontalDivider(color = LogiOnBorder)
}
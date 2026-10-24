package com.example.logion.screens

import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubbleOutline
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.logion.ui.theme.*

// ==============================
// 하단 네비게이션
// 홈, 배송목록, 스캔, 채팅, 더보기 화면 간 이동
// ==============================

@Composable
fun LogiOnBottomNavigation(
    selectedTab: String,
    onTabSelected: (String) -> Unit
) {
    NavigationBar(
        containerColor = MaterialTheme.colorScheme.surface,
        tonalElevation = 0.dp
    ) {
        NavigationBarItem(
            selected = selectedTab == "home",
            onClick = { onTabSelected("home") },
            icon = {
                Icon(
                    imageVector = Icons.Default.Home,
                    contentDescription = "홈",
                    modifier = Modifier.size(21.dp)
                )
            },
            label = { Text("홈") },
            colors = navigationColors()
        )

        NavigationBarItem(
            selected = selectedTab == "route",
            onClick = { onTabSelected("route") },
            icon = {
                Icon(
                    imageVector = Icons.Default.LocationOn,
                    contentDescription = "배송목록",
                    modifier = Modifier.size(21.dp)
                )
            },
            label = { Text("배송목록") },
            colors = navigationColors()
        )

        NavigationBarItem(
            selected = selectedTab == "scan",
            onClick = { onTabSelected("scan") },
            icon = {
                Icon(
                    imageVector = Icons.Default.QrCodeScanner,
                    contentDescription = "스캔",
                    modifier = Modifier.size(21.dp)
                )
            },
            label = { Text("스캔") },
            colors = navigationColors()
        )

        NavigationBarItem(
            selected = selectedTab == "chat",
            onClick = { onTabSelected("chat") },
            icon = {
                Icon(
                    imageVector = Icons.Default.ChatBubbleOutline,
                    contentDescription = "채팅",
                    modifier = Modifier.size(21.dp)
                )
            },
            label = { Text("채팅") },
            colors = navigationColors()
        )

        NavigationBarItem(
            selected = selectedTab == "more",
            onClick = { onTabSelected("more") },
            icon = {
                Icon(
                    imageVector = Icons.Default.Settings,
                    contentDescription = "더보기",
                    modifier = Modifier.size(21.dp)
                )
            },
            label = { Text("더보기") },
            colors = navigationColors()
        )
    }
}

@Composable
private fun navigationColors() = NavigationBarItemDefaults.colors(
    selectedIconColor = LogiOnGreen,
    selectedTextColor = LogiOnGreen,
    unselectedIconColor = LogiOnSubText,
    unselectedTextColor = LogiOnSubText,
    indicatorColor = MaterialTheme.colorScheme.background
)
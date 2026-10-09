package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import com.example.logion.ui.theme.*

// ==============================
// 스캔 화면
// 바코드 스캔과 수기 입력, 이상 보고 기능을 제공함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScanScreen() {
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
                    .verticalScroll(rememberScrollState())
                    .padding(
                        start = 22.dp,
                        end = 22.dp,
                        top = 18.dp,
                        bottom = 16.dp
                    )
            ) {
                // 스캔 화면 제목과 설명
                Text(
                    text = "상품 확인 도구",
                    style = MaterialTheme.typography.labelLarge,
                    color = LogiOnSubText
                )

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = "스캔 센터",
                    style = MaterialTheme.typography.headlineMedium,
                    color = LogiOnText
                )

                Spacer(modifier = Modifier.height(6.dp))

                Text(
                    text = "바코드 또는 배송 라벨을 인식해 작업을 시작하세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(modifier = Modifier.height(16.dp))

                // 실제 카메라 연결 전 사용하는 바코드 스캔 Mock 영역
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(210.dp),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFEAF4E9)
                    ),
                    border = BorderStroke(1.dp, Color(0xFFC5DED0))
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(
                                horizontal = 40.dp,
                                vertical = 18.dp
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(165.dp),
                            shape = RoundedCornerShape(18.dp),
                            color = Color.Transparent,
                            border = BorderStroke(1.dp, Color(0xFF74BD9D))
                        ) {
                            Column(
                                modifier = Modifier.fillMaxSize(),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.QrCodeScanner,
                                    contentDescription = null,
                                    tint = Color(0xFF57997F),
                                    modifier = Modifier.size(40.dp)
                                )

                                Spacer(modifier = Modifier.height(10.dp))

                                Text(
                                    text = "바코드를 프레임 안에 맞춰주세요",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color(0xFF57997F)
                                )
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 추후 ML Kit 또는 카메라 기능과 연결할 스캔 버튼
                Button(
                    onClick = {
                        // TODO: 카메라 스캔 기능 연결
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(49.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = LogiOnGreen2
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.QrCodeScanner,
                        contentDescription = null,
                        modifier = Modifier.size(19.dp)
                    )

                    Spacer(modifier = Modifier.width(7.dp))

                    Text(
                        text = "카메라 스캔 시작",
                        style = MaterialTheme.typography.titleMedium
                    )
                }

                Spacer(modifier = Modifier.height(11.dp))

                // 스캔 실패 시 수기 입력
                ScanMenuCard(
                    icon = Icons.Default.Inventory2,
                    title = "수기 입력",
                    subtitle = "바코드가 보이지 않을 때",
                    warning = false,
                    onClick = {
                        // TODO: 수기 입력 화면 연결
                    }
                )

                Spacer(modifier = Modifier.height(8.dp))

                // 파손, 수량 불일치 등의 예외 상황 보고
                ScanMenuCard(
                    icon = Icons.Default.WarningAmber,
                    title = "이상 보고",
                    subtitle = "파손 · 수량 불일치 · 누락",
                    warning = true,
                    onClick = {
                        // TODO: 이상 보고 화면 연결
                    }
                )

                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}


// 같은 형태의 보조 메뉴를 재사용하기 위한 공통 카드
@Composable
private fun ScanMenuCard(
    icon: ImageVector,
    title: String,
    subtitle: String,
    warning: Boolean,
    onClick: () -> Unit
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(60.dp)
            .clickable(
                interactionSource = interactionSource,
                indication = null
            ) {
                onClick()
            },
        shape = RoundedCornerShape(15.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color.White
        ),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 15.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (warning) LogiOnOrange else LogiOnGreen2,
                modifier = Modifier.size(23.dp)
            )

            Spacer(modifier = Modifier.width(11.dp))

            // 메뉴 제목과 간단한 설명
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(modifier = Modifier.height(1.dp))

                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )
            }

            Icon(
                imageVector = Icons.Default.ArrowForward,
                contentDescription = null,
                tint = LogiOnGreen,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}
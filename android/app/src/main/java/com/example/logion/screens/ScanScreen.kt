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
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.WarningAmber
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
// 카메라 스캔, 수기 입력, 이상 보고 기능을 제공함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScanScreen(
    onCameraScanClick: () -> Unit,
    onManualInputClick: () -> Unit,
    onIssueReportClick: () -> Unit
) {
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
                        bottom = 18.dp
                    )
            ) {
                Text(
                    text = "상품 확인 도구",
                    style = MaterialTheme.typography.labelLarge,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(2.dp))

                Text(
                    text = "스캔 센터",
                    style = MaterialTheme.typography.headlineMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(5.dp))

                Text(
                    text = "바코드를 스캔하거나 직접 입력해 상품 정보를 확인하세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(16.dp))

                // 카메라 스캔 안내 영역
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(210.dp),
                    shape = RoundedCornerShape(20.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color.White
                    ),
                    border = BorderStroke(
                        1.dp,
                        LogiOnBorder
                    )
                ) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Surface(
                            modifier = Modifier.size(165.dp),
                            shape = RoundedCornerShape(18.dp),
                            color = Color(0xFFF8FAF9),
                            border = BorderStroke(
                                1.dp,
                                Color(0xFFCBD9D2)
                            )
                        ) {
                            Column(
                                modifier = Modifier.fillMaxSize(),
                                horizontalAlignment =
                                    Alignment.CenterHorizontally,
                                verticalArrangement =
                                    Arrangement.Center
                            ) {
                                Icon(
                                    imageVector =
                                        Icons.Default.QrCodeScanner,
                                    contentDescription = null,
                                    tint = LogiOnGreen2,
                                    modifier = Modifier.size(50.dp)
                                )

                                Spacer(Modifier.height(10.dp))

                                Text(
                                    text =
                                        "바코드를 프레임 안에 맞춰주세요",
                                    style =
                                        MaterialTheme.typography.bodySmall,
                                    color = LogiOnSubText
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))

                // 실제 CameraX 스캔 화면으로 이동
                Button(
                    onClick = onCameraScanClick,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(49.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = LogiOnGreen2
                    )
                ) {
                    Icon(
                        imageVector =
                            Icons.Default.QrCodeScanner,
                        contentDescription = null,
                        modifier = Modifier.size(19.dp)
                    )

                    Spacer(Modifier.width(7.dp))

                    Text(
                        text = "카메라 스캔 시작",
                        style =
                            MaterialTheme.typography.titleMedium
                    )
                }

                Spacer(Modifier.height(14.dp))

                ScanMenuCard(
                    icon = Icons.Default.Inventory2,
                    title = "수기 입력",
                    subtitle = "바코드가 보이지 않을 때",
                    warning = false,
                    onClick = onManualInputClick
                )

                Spacer(Modifier.height(8.dp))

                ScanMenuCard(
                    icon = Icons.Default.WarningAmber,
                    title = "이상 보고",
                    subtitle =
                        "파손 · 수량 부족 · 오배송 · 온도이상",
                    warning = true,
                    onClick = onIssueReportClick
                )

                Spacer(Modifier.height(12.dp))
            }
        }
    }
}


// 스캔 화면에서 반복 사용하는 메뉴 카드
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
            containerColor = if (warning) {
                LogiOnOrangeLight
            } else {
                Color.White
            }
        ),
        border = BorderStroke(
            1.dp,
            if (warning) {
                Color(0xFFF3C9A8)
            } else {
                LogiOnBorder
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(37.dp),
                shape = RoundedCornerShape(11.dp),
                color = if (warning) {
                    Color(0xFFFFDFC1)
                } else {
                    LogiOnGreenLight
                }
            ) {
                Box(
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = if (warning) {
                            LogiOnOrange
                        } else {
                            LogiOnGreen2
                        },
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            Spacer(Modifier.width(11.dp))

            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = title,
                    style =
                        MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(1.dp))

                Text(
                    text = subtitle,
                    style =
                        MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )
            }
        }
    }
}
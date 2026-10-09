package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
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
import com.example.logion.data.mockDriver
import com.example.logion.ui.theme.*

// ==============================
// 더보기 화면
// 기사 정보와 앱 설정, 추가 작업 메뉴를 보여줌
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoreScreen() {
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
                // 더보기 화면 제목과 설명
                Text(
                    text = "작업 도구",
                    style = MaterialTheme.typography.labelLarge,
                    color = LogiOnSubText
                )

                Spacer(modifier = Modifier.height(2.dp))

                Text(
                    text = "더보기",
                    style = MaterialTheme.typography.headlineMedium,
                    color = LogiOnText
                )

                Spacer(modifier = Modifier.height(5.dp))

                Text(
                    text = "기사 프로필과 기기 상태를 확인하세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(modifier = Modifier.height(15.dp))

                // MockUser에서 가져온 현재 기사 프로필
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(18.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color.White
                    ),
                    border = BorderStroke(1.dp, LogiOnBorder)
                ) {
                    Column(
                        modifier = Modifier.padding(
                            horizontal = 16.dp,
                            vertical = 14.dp
                        )
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Surface(
                                modifier = Modifier.size(50.dp),
                                shape = CircleShape,
                                color = Color(0xFFD7F1E6)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Text(
                                        text = mockDriver.initial,
                                        style = MaterialTheme.typography.headlineSmall,
                                        color = LogiOnGreen2
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.width(12.dp))

                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "${mockDriver.name} 기사님",
                                    style = MaterialTheme.typography.titleLarge,
                                    color = LogiOnText
                                )

                                Spacer(modifier = Modifier.height(2.dp))

                                Text(
                                    text = "${mockDriver.area} · 차량 ${mockDriver.vehicleNumber}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = LogiOnSubText
                                )
                            }

                            Icon(
                                imageVector = Icons.Default.ChevronRight,
                                contentDescription = null,
                                tint = LogiOnText,
                                modifier = Modifier.size(20.dp)
                            )
                        }

                        Spacer(modifier = Modifier.height(11.dp))
                        HorizontalDivider(color = LogiOnBorder)
                        Spacer(modifier = Modifier.height(10.dp))

                        // 오프라인 데이터 저장 상태 표시
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Surface(
                                modifier = Modifier.size(16.dp),
                                shape = CircleShape,
                                color = Color(0xFFDDF4EA)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Surface(
                                        modifier = Modifier.size(7.dp),
                                        shape = CircleShape,
                                        color = Color(0xFF67D2AD)
                                    ) {}
                                }
                            }

                            Spacer(modifier = Modifier.width(6.dp))

                            Text(
                                text = "오프라인 캐시 정상",
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )

                            Spacer(modifier = Modifier.weight(1f))

                            Text(
                                text = "98%",
                                style = MaterialTheme.typography.titleSmall,
                                color = LogiOnGreen2
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(11.dp))

                // 기사 개인 설정 메뉴
                MoreMenuCard(
                    icon = Icons.Default.VolumeUp,
                    title = "음성 안내 설정"
                )

                Spacer(modifier = Modifier.height(7.dp))

                MoreMenuCard(
                    icon = Icons.Default.Tune,
                    title = "운송 환경 설정"
                )

                Spacer(modifier = Modifier.height(7.dp))

                MoreMenuCard(
                    icon = Icons.Default.HelpOutline,
                    title = "도움말 및 문의"
                )

                Spacer(modifier = Modifier.height(10.dp))

                // 추후 공지, 운행 리포트, 관리자 기능과 연결할 영역
                AdditionalMenuCard()

                Spacer(modifier = Modifier.height(10.dp))
            }
        }
    }
}


// 더보기 화면에서 같은 형태로 사용하는 설정 메뉴 카드
@Composable
private fun MoreMenuCard(
    icon: ImageVector,
    title: String
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(55.dp)
            .clickable(
                interactionSource = interactionSource,
                indication = null
            ) {
                // TODO: 각 설정 화면 연결
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
                tint = LogiOnGreen2,
                modifier = Modifier.size(21.dp)
            )

            Spacer(modifier = Modifier.width(11.dp))

            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = LogiOnText,
                modifier = Modifier.weight(1f)
            )

            Icon(
                imageVector = Icons.Default.ChevronRight,
                contentDescription = null,
                tint = LogiOnGreen,
                modifier = Modifier.size(19.dp)
            )
        }
    }
}


// 공지사항, 운행 리포트 등 추가 작업 메뉴
@Composable
private fun AdditionalMenuCard() {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                interactionSource = interactionSource,
                indication = null
            ) {
                // TODO: 추가 작업 화면 연결
            },
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = Color.Transparent
        ),
        border = BorderStroke(
            1.dp,
            Color(0xFFBFD8CC)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    horizontal = 14.dp,
                    vertical = 12.dp
                ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(34.dp),
                shape = RoundedCornerShape(10.dp),
                color = Color.White,
                border = BorderStroke(
                    1.dp,
                    Color(0xFFBED8CB)
                )
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = null,
                        tint = LogiOnSubText,
                        modifier = Modifier.size(17.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.width(9.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "공지사항 · 운행 리포트",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnText
                )

                Spacer(modifier = Modifier.height(1.dp))

                Text(
                    text = "관리자 연결 및 추가 작업 도구",
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )
            }

            Icon(
                imageVector = Icons.Default.ChevronRight,
                contentDescription = null,
                tint = LogiOnGreen,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}
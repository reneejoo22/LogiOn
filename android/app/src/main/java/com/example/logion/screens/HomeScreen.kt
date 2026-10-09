package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.logion.data.deliveryStops
import com.example.logion.data.mockDriver
import com.example.logion.model.DeliveryStop
import com.example.logion.ui.theme.*
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlinx.coroutines.delay

// ==============================
// 홈 화면
// 오늘의 배송 진행 상황과 다음 배송 정보를 보여줌
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    completedStops: Set<Int>,
    isListening: Boolean,
    onStopClick: (DeliveryStop) -> Unit
) {
    // 완료된 배송 수와 전체 진행률 계산
    val completedCount = completedStops.size
    val progress = completedCount.toFloat() / deliveryStops.size.toFloat()

    // 완료되지 않은 배송지 중 첫 번째 장소를 다음 배송지로 사용
    val nextStop = deliveryStops.firstOrNull {
        !completedStops.contains(it.id)
    }

    // 현재 날짜와 시간
    var currentTime by remember {
        mutableStateOf(LocalDateTime.now())
    }

    LaunchedEffect(Unit) {
        while (true) {
            currentTime = LocalDateTime.now()
            delay(60_000L)
        }
    }

    // 날짜, 요일, 오전/오후, 시간 표시
    val currentTimeText = remember(currentTime) {
        val formatter = DateTimeFormatter.ofPattern(
            "yyyy년 M월 d일 EEEE · a h:mm",
            Locale.KOREAN
        )
        currentTime.format(formatter)
    }

    val stopClickInteraction = remember {
        MutableInteractionSource()
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
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(
                    start = 22.dp,
                    end = 22.dp,
                    top = 18.dp,
                    bottom = 18.dp
                )
            ) {
                item {
                    // 현재 날짜, 시간과 로그인된 기사 정보
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = currentTimeText,
                                style = MaterialTheme.typography.labelLarge,
                                color = LogiOnSubText
                            )

                            Spacer(modifier = Modifier.height(5.dp))

                            Text(
                                text = "안녕하세요, ${mockDriver.name} 기사님",
                                style = MaterialTheme.typography.headlineMedium,
                                color = LogiOnText
                            )
                        }

                        Surface(
                            modifier = Modifier.size(48.dp),
                            shape = CircleShape,
                            color = Color(0xFFD7F1E6)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Text(
                                    text = mockDriver.initial,
                                    fontSize = 19.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = LogiOnGreen2
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // 오늘 전체 배송 진행률
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(20.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = LogiOnGreen
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(
                                horizontal = 18.dp,
                                vertical = 14.dp
                            )
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Surface(
                                        modifier = Modifier.size(9.dp),
                                        shape = CircleShape,
                                        color = Color(0xFF62D9AD)
                                    ) {}

                                    Spacer(modifier = Modifier.width(7.dp))

                                    Text(
                                        text = "오늘 배송",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color.White
                                    )
                                }

                                Spacer(modifier = Modifier.weight(1f))

                                Text(
                                    text = "$completedCount / ${deliveryStops.size}",
                                    fontSize = 21.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }

                            Spacer(modifier = Modifier.height(6.dp))

                            Text(
                                text = "완료율 ${(progress * 100).toInt()}%",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.White.copy(alpha = 0.78f)
                            )

                            Spacer(modifier = Modifier.height(10.dp))

                            LinearProgressIndicator(
                                progress = { progress },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(6.dp),
                                color = Color(0xFF62D9AD),
                                trackColor = Color.White.copy(alpha = 0.18f)
                            )

                            Spacer(modifier = Modifier.height(9.dp))

                            Row(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    text = "출발 09:40",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color.White.copy(alpha = 0.8f)
                                )

                                Spacer(modifier = Modifier.weight(1f))

                                Text(
                                    text = "예상 종료 12:05",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color.White.copy(alpha = 0.8f)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    // AI가 추천한 다음 배송지 안내
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "AI가 정리한 오늘의 우선순위",
                                style = MaterialTheme.typography.labelLarge,
                                color = LogiOnSubText
                            )

                            Spacer(modifier = Modifier.height(3.dp))

                            Text(
                                text = if (nextStop != null) {
                                    "다음 배송을 준비하세요"
                                } else {
                                    "오늘 배송을 모두 완료했어요"
                                },
                                style = MaterialTheme.typography.headlineSmall,
                                color = LogiOnText
                            )
                        }

                        Spacer(modifier = Modifier.weight(1f))

                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = null,
                            tint = LogiOnGreen,
                            modifier = Modifier.size(22.dp)
                        )
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // 남아 있는 배송지가 있을 때만 다음 배송 카드 표시
                    if (nextStop != null) {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable(
                                    interactionSource = stopClickInteraction,
                                    indication = null
                                ) {
                                    onStopClick(nextStop)
                                },
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = Color.White
                            ),
                            border = BorderStroke(1.dp, LogiOnBorder)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Surface(
                                        shape = RoundedCornerShape(30.dp),
                                        color = LogiOnGreenLight
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(
                                                horizontal = 8.dp,
                                                vertical = 5.dp
                                            ),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.AutoAwesome,
                                                contentDescription = null,
                                                tint = LogiOnGreen2,
                                                modifier = Modifier.size(13.dp)
                                            )

                                            Spacer(modifier = Modifier.width(3.dp))

                                            Text(
                                                text = "AI 추천",
                                                style = MaterialTheme.typography.labelLarge,
                                                color = LogiOnGreen2
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.weight(1f))

                                    Text(
                                        text = "도착까지 ${nextStop.distance}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }

                                Spacer(modifier = Modifier.height(13.dp))

                                // 다음 배송지의 기본 정보
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Storefront,
                                        contentDescription = null,
                                        tint = LogiOnGreen2,
                                        modifier = Modifier.size(23.dp)
                                    )

                                    Spacer(modifier = Modifier.width(10.dp))

                                    Column(modifier = Modifier.weight(1f)) {
                                        Text(
                                            text = nextStop.name,
                                            style = MaterialTheme.typography.titleLarge,
                                            color = LogiOnText
                                        )

                                        Spacer(modifier = Modifier.height(2.dp))

                                        Text(
                                            text = nextStop.address,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = LogiOnSubText
                                        )
                                    }

                                    Icon(
                                        imageVector = Icons.Default.ChevronRight,
                                        contentDescription = null,
                                        tint = LogiOnGreen2,
                                        modifier = Modifier.size(21.dp)
                                    )
                                }

                                Spacer(modifier = Modifier.height(11.dp))

                                // 도착 예정 시간과 배송 박스 수
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.AccessTime,
                                        contentDescription = null,
                                        tint = Color(0xFF91AAA0),
                                        modifier = Modifier.size(16.dp)
                                    )

                                    Spacer(modifier = Modifier.width(4.dp))

                                    Text(
                                        text = "${nextStop.eta} 도착 예정",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )

                                    Spacer(modifier = Modifier.width(12.dp))

                                    Icon(
                                        imageVector = Icons.Default.Inventory2,
                                        contentDescription = null,
                                        tint = Color(0xFF91AAA0),
                                        modifier = Modifier.size(16.dp)
                                    )

                                    Spacer(modifier = Modifier.width(4.dp))

                                    Text(
                                        text = "박스 ${nextStop.boxes}개",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }

                                Spacer(modifier = Modifier.height(12.dp))

                                // 추후 지도 API 또는 지도 화면과 연결할 버튼
                                Button(
                                    onClick = {
                                        // TODO: 지도 화면 연결
                                    },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .height(48.dp),
                                    shape = RoundedCornerShape(14.dp),
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = LogiOnGreenLight,
                                        contentColor = LogiOnGreen2
                                    )
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.LocationOn,
                                        contentDescription = null,
                                        modifier = Modifier.size(19.dp)
                                    )

                                    Spacer(modifier = Modifier.width(7.dp))

                                    Text(
                                        text = "배송지 위치 보기",
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(12.dp))

                        // 다음 배송 전 미리 확인해야 할 상품 안내
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(17.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = LogiOnOrangeLight
                            ),
                            border = BorderStroke(
                                1.dp,
                                Color(0xFFF3C9A8)
                            )
                        ) {
                            Row(
                                modifier = Modifier.padding(13.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Surface(
                                    modifier = Modifier.size(38.dp),
                                    shape = RoundedCornerShape(11.dp),
                                    color = Color(0xFFFFDFC1)
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Icon(
                                            imageVector = Icons.Default.WarningAmber,
                                            contentDescription = null,
                                            tint = LogiOnOrange,
                                            modifier = Modifier.size(21.dp)
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.width(11.dp))

                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "배송 전 확인이 필요해요",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = LogiOnText
                                    )

                                    Spacer(modifier = Modifier.height(2.dp))

                                    Text(
                                        text = "냉장 상품 4박스가 별도 구역에 있습니다.",
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
                        }

                        Spacer(modifier = Modifier.height(13.dp))
                    }

                    // VoiceDock과 연결된 현재 음성 입력 상태 표시
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = null,
                            tint = LogiOnGreen2,
                            modifier = Modifier.size(16.dp)
                        )

                        Spacer(modifier = Modifier.width(6.dp))

                        Text(
                            text = if (isListening) {
                                "음성 입력 중입니다."
                            } else {
                                "음성 입력을 종료했습니다."
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = LogiOnSubText
                        )
                    }

                    Spacer(modifier = Modifier.height(10.dp))
                }
            }
        }
    }
}
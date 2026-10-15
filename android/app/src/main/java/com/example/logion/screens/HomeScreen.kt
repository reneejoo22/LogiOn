package com.example.logion.screens

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.util.Log
import android.widget.Toast
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.logion.data.mockDriver
import com.example.logion.data.remote.DriverResponse
import com.example.logion.data.remote.RetrofitClient
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
    stops: List<DeliveryStop>,
    completedStops: Set<Int>,
    departAt: String?,
    estEndAt: String?,
    isListening: Boolean,
    onStopClick: (DeliveryStop) -> Unit
) {
    val context = LocalContext.current

    // 서버 응답 전에는 Mock 기사 정보를 사용
    var driver by remember {
        mutableStateOf<DriverResponse?>(null)
    }

    // 홈 화면이 열리면 실제 기사 정보를 서버에서 불러옴
    LaunchedEffect(Unit) {
        try {
            driver = RetrofitClient.api.getDriver()

            Log.d(
                "API_DRIVER",
                "홈 기사 정보 불러오기 성공: ${driver?.name}"
            )
        } catch (e: Exception) {
            Log.e(
                "API_DRIVER",
                "홈 기사 정보 불러오기 실패",
                e
            )
        }
    }

    // 완료된 배송 수와 전체 진행률
    val completedCount = completedStops.size

    val progress = if (stops.isEmpty()) {
        0f
    } else {
        completedCount.toFloat() / stops.size.toFloat()
    }

    // 완료되지 않은 첫 번째 배송지를 다음 배송지로 사용
    val nextStop = stops.firstOrNull {
        !completedStops.contains(it.id)
    }

    // 서버에서 받은 배송 시간
    val departTimeText = formatRouteTime(departAt)
    val endTimeText = formatRouteTime(estEndAt)

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
                    // 현재 날짜, 시간과 기사 정보
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(
                            modifier = Modifier.weight(1f)
                        ) {
                            Text(
                                text = currentTimeText,
                                style = MaterialTheme.typography.labelLarge,
                                color = LogiOnSubText
                            )

                            Spacer(Modifier.height(5.dp))

                            Text(
                                text = "안녕하세요, ${
                                    driver?.name ?: mockDriver.name
                                } 기사님",
                                style = MaterialTheme.typography.headlineMedium,
                                color = LogiOnText
                            )
                        }

                        Surface(
                            modifier = Modifier.size(48.dp),
                            shape = CircleShape,
                            color = Color(0xFFD7F1E6)
                        ) {
                            Box(
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = driver?.initial
                                        ?: mockDriver.initial,
                                    fontSize = 19.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = LogiOnGreen2
                                )
                            }
                        }
                    }

                    Spacer(Modifier.height(16.dp))

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

                                    Spacer(Modifier.width(7.dp))

                                    Text(
                                        text = "오늘 배송",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = Color.White
                                    )
                                }

                                Spacer(Modifier.weight(1f))

                                Text(
                                    text = "$completedCount / ${stops.size}",
                                    fontSize = 21.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }

                            Spacer(Modifier.height(6.dp))

                            Text(
                                text = "완료율 ${(progress * 100).toInt()}%",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color.White.copy(
                                    alpha = 0.78f
                                )
                            )

                            Spacer(Modifier.height(10.dp))

                            LinearProgressIndicator(
                                progress = {
                                    progress
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(6.dp),
                                color = Color(0xFF62D9AD),
                                trackColor = Color.White.copy(
                                    alpha = 0.18f
                                )
                            )

                            Spacer(Modifier.height(9.dp))

                            // 서버에서 받은 출발 및 예상 종료 시간
                            Row(
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                Text(
                                    text = "출발 $departTimeText",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color.White.copy(
                                        alpha = 0.8f
                                    )
                                )

                                Spacer(Modifier.weight(1f))

                                Text(
                                    text = "예상 종료 $endTimeText",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = Color.White.copy(
                                        alpha = 0.8f
                                    )
                                )
                            }
                        }
                    }

                    Spacer(Modifier.height(20.dp))

                    // 다음 배송지 추천 영역
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

                            Spacer(Modifier.height(3.dp))

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

                        Spacer(Modifier.weight(1f))

                        Icon(
                            imageVector = Icons.Default.AutoAwesome,
                            contentDescription = null,
                            tint = LogiOnGreen,
                            modifier = Modifier.size(22.dp)
                        )
                    }

                    Spacer(Modifier.height(12.dp))

                    // 남아 있는 배송지가 있을 때만 표시
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
                            border = BorderStroke(
                                1.dp,
                                LogiOnBorder
                            )
                        ) {
                            Column(
                                modifier = Modifier.padding(16.dp)
                            ) {
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

                                            Spacer(Modifier.width(3.dp))

                                            Text(
                                                text = "AI 추천",
                                                style = MaterialTheme.typography.labelLarge,
                                                color = LogiOnGreen2
                                            )
                                        }
                                    }

                                    Spacer(Modifier.weight(1f))

                                    Text(
                                        text = "도착까지 ${nextStop.distance}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }

                                Spacer(Modifier.height(13.dp))

                                // 다음 배송지 기본 정보
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Storefront,
                                        contentDescription = null,
                                        tint = LogiOnGreen2,
                                        modifier = Modifier.size(23.dp)
                                    )

                                    Spacer(Modifier.width(10.dp))

                                    Column(
                                        modifier = Modifier.weight(1f)
                                    ) {
                                        Text(
                                            text = nextStop.name,
                                            style = MaterialTheme.typography.titleLarge,
                                            color = LogiOnText
                                        )

                                        Spacer(Modifier.height(2.dp))

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

                                Spacer(Modifier.height(11.dp))

                                // 도착 예정 시간과 박스 수
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.AccessTime,
                                        contentDescription = null,
                                        tint = Color(0xFF91AAA0),
                                        modifier = Modifier.size(16.dp)
                                    )

                                    Spacer(Modifier.width(4.dp))

                                    Text(
                                        text = "${nextStop.eta} 도착 예정",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )

                                    Spacer(Modifier.width(12.dp))

                                    Icon(
                                        imageVector = Icons.Default.Inventory2,
                                        contentDescription = null,
                                        tint = Color(0xFF91AAA0),
                                        modifier = Modifier.size(16.dp)
                                    )

                                    Spacer(Modifier.width(4.dp))

                                    Text(
                                        text = "박스 ${nextStop.boxes}개",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }

                                Spacer(Modifier.height(12.dp))

                                // 서버 좌표 사용
                                Button(
                                    onClick = {
                                        val lat = nextStop.lat
                                        val lng = nextStop.lng

                                        val uri =
                                            if (
                                                lat != null &&
                                                lng != null
                                            ) {
                                                val query = Uri.encode(
                                                    "$lat,$lng(${nextStop.name})"
                                                )

                                                Uri.parse(
                                                    "geo:$lat,$lng?q=$query"
                                                )
                                            } else {
                                                // 좌표가 없을 때만 주소 검색
                                                val address = Uri.encode(
                                                    nextStop.address
                                                )

                                                Uri.parse(
                                                    "geo:0,0?q=$address"
                                                )
                                            }

                                        try {
                                            context.startActivity(
                                                Intent(
                                                    Intent.ACTION_VIEW,
                                                    uri
                                                )
                                            )
                                        } catch (
                                            e: ActivityNotFoundException
                                        ) {
                                            Toast.makeText(
                                                context,
                                                "사용 가능한 지도 앱이 없습니다.",
                                                Toast.LENGTH_SHORT
                                            ).show()
                                        }
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

                                    Spacer(Modifier.width(7.dp))

                                    Text(
                                        text = "배송지 위치 보기",
                                        style = MaterialTheme.typography.titleMedium
                                    )
                                }
                            }
                        }

                        Spacer(Modifier.height(12.dp))

                        // 서버에 배송 전 확인사항이 있을 때만 표시
                        nextStop.notice
                            ?.takeIf {
                                it.isNotBlank()
                            }
                            ?.let { notice ->
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
                                            Box(
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.WarningAmber,
                                                    contentDescription = null,
                                                    tint = LogiOnOrange,
                                                    modifier = Modifier.size(21.dp)
                                                )
                                            }
                                        }

                                        Spacer(Modifier.width(11.dp))

                                        Column(
                                            modifier = Modifier.weight(1f)
                                        ) {
                                            Text(
                                                text = "배송 전 확인이 필요해요",
                                                style = MaterialTheme.typography.titleMedium,
                                                color = LogiOnText
                                            )

                                            Spacer(Modifier.height(2.dp))

                                            Text(
                                                text = notice,
                                                style = MaterialTheme.typography.bodySmall,
                                                color = LogiOnSubText
                                            )
                                        }
                                    }
                                }

                                Spacer(Modifier.height(13.dp))
                            }

                        // VoiceDock과 연결된 음성 입력 상태
                        Row(
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Check,
                                contentDescription = null,
                                tint = LogiOnGreen2,
                                modifier = Modifier.size(16.dp)
                            )

                            Spacer(Modifier.width(6.dp))

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

                        Spacer(Modifier.height(10.dp))
                    }
                }
            }
        }
    }
}

// 백엔드 날짜+시간 문자열에서 HH:mm만 표시
private fun formatRouteTime(
    value: String?
): String {
    if (value.isNullOrBlank()) {
        return "-"
    }

    return if ("T" in value) {
        value.substringAfter("T").take(5)
    } else {
        value.take(5)
    }
}
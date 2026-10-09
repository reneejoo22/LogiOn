package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.logion.data.deliveryStops
import com.example.logion.model.DeliveryStop
import com.example.logion.ui.theme.*

// ==============================
// 배송목록 화면
// 배송지 상태를 확인하고 배송 완료 여부를 관리함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RouteScreen(
    completedStops: Set<Int>,
    onStopClick: (DeliveryStop) -> Unit,
    onQuickToggleComplete: (DeliveryStop) -> Unit
) {
    // 사용자가 선택한 배송목록 필터
    var selectedFilter by remember {
        mutableStateOf("all")
    }

    // 완료되지 않은 배송지 중 첫 번째 장소를 현재 진행 중인 배송으로 지정
    val activeStop = deliveryStops.firstOrNull {
        !completedStops.contains(it.id)
    }

    // 선택한 필터에 따라 화면에 표시할 배송지 목록 결정
    val visibleStops = when (selectedFilter) {
        "active" -> activeStop?.let { listOf(it) } ?: emptyList()

        "completed" -> deliveryStops.filter {
            completedStops.contains(it.id)
        }

        else -> deliveryStops
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
                    bottom = 20.dp
                )
            ) {
                // 배송목록 제목과 상태 필터
                item {
                    Text(
                        text = "오늘의 운송 경로",
                        style = MaterialTheme.typography.labelLarge,
                        color = LogiOnSubText
                    )

                    Spacer(modifier = Modifier.height(3.dp))

                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            text = "배송목록",
                            style = MaterialTheme.typography.headlineSmall,
                            color = LogiOnText
                        )

                        Spacer(modifier = Modifier.width(5.dp))

                        Text(
                            text = "${deliveryStops.size}곳",
                            style = MaterialTheme.typography.headlineSmall,
                            color = LogiOnGreen2
                        )
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    Text(
                        text = "성수 권역 · 마지막 동기화 09:38",
                        style = MaterialTheme.typography.bodySmall,
                        color = LogiOnSubText
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(7.dp)
                    ) {
                        RouteFilterChip(
                            text = "전체 ${deliveryStops.size}",
                            selected = selectedFilter == "all",
                            onClick = {
                                selectedFilter = "all"
                            }
                        )

                        RouteFilterChip(
                            text = "진행 중 ${if (activeStop != null) 1 else 0}",
                            selected = selectedFilter == "active",
                            onClick = {
                                selectedFilter = "active"
                            }
                        )

                        RouteFilterChip(
                            text = "완료 ${completedStops.size}",
                            selected = selectedFilter == "completed",
                            onClick = {
                                selectedFilter = "completed"
                            }
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                }

                // 선택한 필터에 맞는 배송지 카드 표시
                items(
                    items = visibleStops,
                    key = { it.id }
                ) { stop ->
                    val completed = completedStops.contains(stop.id)
                    val isActive = activeStop?.id == stop.id

                    DeliveryStopCard(
                        stop = stop,
                        completed = completed,
                        isActive = isActive,
                        onClick = {
                            onStopClick(stop)
                        },
                        onToggleComplete = {
                            onQuickToggleComplete(stop)
                        }
                    )

                    Spacer(modifier = Modifier.height(9.dp))
                }

                // 추후 긴급 배차나 기사 메모 기능 추가
                item {
                    Spacer(modifier = Modifier.height(2.dp))

                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(90.dp),
                        shape = RoundedCornerShape(17.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = LogiOnBackground
                        ),
                        border = BorderStroke(
                            1.dp,
                            Color(0xFFBDD8CD)
                        )
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxSize()
                                .padding(horizontal = 15.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.Center
                        ) {
                            Surface(
                                modifier = Modifier.size(36.dp),
                                shape = RoundedCornerShape(10.dp),
                                color = Color.White,
                                border = BorderStroke(
                                    1.dp,
                                    Color(0xFFBDD8CD)
                                )
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Default.Add,
                                        contentDescription = null,
                                        tint = LogiOnSubText,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.width(10.dp))

                            Text(
                                text = "추가 배송지 · 긴급 배차 · 기사 메모",
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))
                }
            }
        }
    }
}


// 전체, 진행 중, 완료 상태를 선택하는 공통 필터 버튼
@Composable
private fun RouteFilterChip(
    text: String,
    selected: Boolean,
    onClick: () -> Unit
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Surface(
        modifier = Modifier.clickable(
            interactionSource = interactionSource,
            indication = null
        ) {
            onClick()
        },
        shape = RoundedCornerShape(30.dp),
        color = if (selected) LogiOnGreen else Color.White,
        border = if (selected) {
            null
        } else {
            BorderStroke(1.dp, LogiOnBorder)
        }
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(
                horizontal = 13.dp,
                vertical = 7.dp
            ),
            style = MaterialTheme.typography.bodySmall,
            color = if (selected) Color.White else LogiOnSubText
        )
    }
}


// 배송지 하나의 상태와 정보를 표시하는 공통 카드
@Composable
private fun DeliveryStopCard(
    stop: DeliveryStop,
    completed: Boolean,
    isActive: Boolean,
    onClick: () -> Unit,
    onToggleComplete: () -> Unit
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    val statusText = when {
        completed -> "완료"
        isActive -> "다음 배송"
        else -> "예정"
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                interactionSource = interactionSource,
                indication = null
            ) {
                onClick()
            },
        shape = RoundedCornerShape(17.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (completed) {
                Color(0xFFFAFCFA)
            } else {
                Color.White
            }
        ),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Row(
            modifier = Modifier.padding(
                horizontal = 14.dp,
                vertical = 13.dp
            ),
            verticalAlignment = Alignment.Top
        ) {
            // 왼쪽에는 배송 순서, 완료된 경우 체크 아이콘 표시
            Surface(
                modifier = Modifier.size(34.dp),
                shape = CircleShape,
                color = if (completed) {
                    LogiOnGreen2
                } else {
                    Color(0xFFF1F8F5)
                }
            ) {
                Box(contentAlignment = Alignment.Center) {
                    if (completed) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(17.dp)
                        )
                    } else {
                        Text(
                            text = stop.id.toString(),
                            style = MaterialTheme.typography.titleSmall,
                            color = LogiOnGreen2
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.width(10.dp))

            // 배송지 정보
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = stop.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (completed) {
                            LogiOnSubText
                        } else {
                            LogiOnText
                        }
                    )

                    Spacer(modifier = Modifier.weight(1f))

                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = when {
                            completed -> LogiOnGreen2
                            isActive -> LogiOnOrangeLight
                            else -> Color(0xFFF3F4F2)
                        }
                    ) {
                        Text(
                            text = statusText,
                            modifier = Modifier.padding(
                                horizontal = 9.dp,
                                vertical = 4.dp
                            ),
                            style = MaterialTheme.typography.labelSmall,
                            color = when {
                                completed -> Color.White
                                isActive -> LogiOnOrange
                                else -> LogiOnSubText
                            }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(3.dp))

                Text(
                    text = stop.address,
                    style = MaterialTheme.typography.bodySmall,
                    color = Color(0xFF94A69E)
                )

                Spacer(modifier = Modifier.height(8.dp))

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.AccessTime,
                        contentDescription = null,
                        tint = Color(0xFFA1B2AA),
                        modifier = Modifier.size(15.dp)
                    )

                    Spacer(modifier = Modifier.width(3.dp))

                    Text(
                        text = stop.eta,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF8FA198)
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    Icon(
                        imageVector = Icons.Default.Inventory2,
                        contentDescription = null,
                        tint = Color(0xFFA1B2AA),
                        modifier = Modifier.size(15.dp)
                    )

                    Spacer(modifier = Modifier.width(3.dp))

                    Text(
                        text = "${stop.boxes}박스",
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF8FA198)
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    Text(
                        text = stop.distance,
                        style = MaterialTheme.typography.bodySmall,
                        color = Color(0xFF8FA198)
                    )
                }
            }

            Spacer(modifier = Modifier.width(5.dp))

            // 목록에서 바로 배송 완료 또는 완료 취소
            IconButton(
                onClick = onToggleComplete,
                modifier = Modifier.size(38.dp)
            ) {
                Surface(
                    modifier = Modifier.size(36.dp),
                    shape = RoundedCornerShape(10.dp),
                    color = if (completed) {
                        LogiOnGreen2
                    } else {
                        Color.White
                    },
                    border = if (completed) {
                        null
                    } else {
                        BorderStroke(
                            1.dp,
                            Color(0xFFCBE3D8)
                        )
                    }
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = if (completed) {
                                "배송 완료 취소"
                            } else {
                                "배송 완료"
                            },
                            tint = if (completed) {
                                Color.White
                            } else {
                                LogiOnGreen2
                            },
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}
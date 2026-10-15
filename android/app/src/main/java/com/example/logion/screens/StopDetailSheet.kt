package com.example.logion.screens

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.example.logion.data.remote.StopDetailResponse
import com.example.logion.data.remote.ZoneResponse
import com.example.logion.model.DeliveryStop
import com.example.logion.ui.theme.*

// ==============================
// 배송지 상세 BottomSheet
// 상품 확인, 연락, 길 안내, 배송 상태를 관리함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StopDetailSheet(
    stop: DeliveryStop,
    detail: StopDetailResponse,
    isProcessing: Boolean,
    onZoneToggle: (ZoneResponse) -> Unit,
    onClose: () -> Unit,
    onComplete: () -> Unit,
    onCancelComplete: () -> Unit,
    onIssueReport: () -> Unit
) {
    val context = LocalContext.current
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = false)
    val isCompleted = detail.status == "done"
    val zones = detail.zones
    val checkedCount = zones.count { it.checked }
    val allChecked = zones.isNotEmpty() && zones.all { it.checked }

    ModalBottomSheet(
        onDismissRequest = { if (!isProcessing) onClose() },
        sheetState = sheetState,
        containerColor = LogiOnBackground,
        dragHandle = {
            Surface(
                modifier = Modifier.padding(vertical = 8.dp).width(48.dp).height(4.dp),
                shape = RoundedCornerShape(20.dp),
                color = Color(0xFFBED0C8)
            ) {}
        }
    ) {
        CompositionLocalProvider(
            LocalOverscrollFactory provides null,
            LocalRippleConfiguration provides null
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState())
                    .padding(start = 16.dp, end = 16.dp, bottom = 18.dp)
            ) {
                // 배송지 기본 정보
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (isCompleted) "배송지 상세 · 배송 완료"
                            else "배송지 상세 · ${stop.eta} 도착 예정",
                            style = MaterialTheme.typography.labelLarge,
                            color = LogiOnSubText
                        )

                        Spacer(Modifier.height(4.dp))

                        Text(
                            text = stop.name,
                            style = MaterialTheme.typography.headlineSmall,
                            color = LogiOnText
                        )

                        Spacer(Modifier.height(3.dp))

                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.LocationOn,
                                contentDescription = null,
                                tint = Color(0xFF96ABA1),
                                modifier = Modifier.size(15.dp)
                            )
                            Spacer(Modifier.width(4.dp))
                            Text(
                                text = stop.address,
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )
                        }
                    }

                    IconButton(
                        onClick = onClose,
                        enabled = !isProcessing,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "닫기",
                            tint = if (isProcessing) LogiOnSubText else LogiOnGreen,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                // 빠른 기능
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(7.dp)
                ) {
                    DetailActionButton(
                        title = "매장 연락",
                        icon = Icons.Default.Phone,
                        modifier = Modifier.weight(1f)
                    ) {
                        val phone = detail.store.phone
                        if (!phone.isNullOrBlank()) {
                            try {
                                context.startActivity(
                                    Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone"))
                                )
                            } catch (e: ActivityNotFoundException) {
                                Toast.makeText(
                                    context,
                                    "전화 앱을 실행할 수 없습니다.",
                                    Toast.LENGTH_SHORT
                                ).show()
                            }
                        } else {
                            Toast.makeText(
                                context,
                                "등록된 매장 전화번호가 없습니다.",
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                    }

                    DetailActionButton(
                        title = "길 안내",
                        icon = Icons.Default.LocationOn,
                        modifier = Modifier.weight(1f)
                    ) {
                        val lat = detail.store.lat
                        val lng = detail.store.lng

                        val uri = if (lat != null && lng != null) {
                            val query = Uri.encode("$lat,$lng(${detail.store.name})")
                            Uri.parse("geo:$lat,$lng?q=$query")
                        } else {
                            Uri.parse("geo:0,0?q=${Uri.encode(detail.store.address)}")
                        }

                        try {
                            context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                        } catch (e: ActivityNotFoundException) {
                            Toast.makeText(
                                context,
                                "사용 가능한 지도 앱이 없습니다.",
                                Toast.LENGTH_SHORT
                            ).show()
                        }
                    }

                    DetailActionButton(
                        title = "이상 보고",
                        icon = Icons.Default.WarningAmber,
                        modifier = Modifier.weight(1f),
                        warning = true,
                        enabled = !isProcessing,
                        onClick = onIssueReport
                    )
                }

                Spacer(Modifier.height(12.dp))

                // 상품 확인 진행률
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(15.dp),
                    colors = CardDefaults.cardColors(containerColor = LogiOnGreenLight),
                    border = BorderStroke(1.dp, Color(0xFFD0E6DB))
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "상품 확인",
                                style = MaterialTheme.typography.titleMedium,
                                color = LogiOnText
                            )
                            Spacer(Modifier.weight(1f))
                            Text(
                                text = "$checkedCount / ${zones.size} 구역 확인",
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )
                        }

                        Spacer(Modifier.height(8.dp))

                        LinearProgressIndicator(
                            progress = {
                                if (zones.isEmpty()) 0f
                                else checkedCount.toFloat() / zones.size
                            },
                            modifier = Modifier.fillMaxWidth().height(6.dp),
                            color = LogiOnGreen2,
                            trackColor = Color(0xFFD5E7DE)
                        )
                    }
                }

                Spacer(Modifier.height(8.dp))

                // 상품 구역
                zones.forEachIndexed { index, zone ->
                    ProductCheckCard(
                        title = zone.label,
                        rightText = if (zone.checked) "확인" else "${zone.boxes}박스",
                        checked = zone.checked,
                        enabled = !isCompleted && !isProcessing,
                        onClick = { onZoneToggle(zone) }
                    )

                    if (index < zones.lastIndex) Spacer(Modifier.height(6.dp))
                }

                Spacer(Modifier.height(12.dp))

                // 배송 완료 / 취소
                Button(
                    onClick = {
                        if (isCompleted) onCancelComplete()
                        else onComplete()
                    },
                    enabled = !isProcessing && (isCompleted || allChecked),
                    modifier = Modifier.fillMaxWidth().height(50.dp),
                    shape = RoundedCornerShape(15.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isCompleted) LogiOnOrange else LogiOnGreen,
                        disabledContainerColor = Color(0xFFB8C9C2),
                        disabledContentColor = Color.White
                    )
                ) {
                    if (isProcessing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = Color.White
                        )
                        Spacer(Modifier.width(7.dp))
                        Text("처리 중...", style = MaterialTheme.typography.titleMedium)
                    } else {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = when {
                                isCompleted -> "배송 완료 취소"
                                allChecked -> "배송 완료 처리"
                                else -> "모든 상품을 확인해 주세요"
                            },
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }

                Spacer(Modifier.height(8.dp))

                // 저장 상태
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (isProcessing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(13.dp),
                            strokeWidth = 2.dp,
                            color = LogiOnGreen2
                        )
                    } else {
                        Surface(
                            modifier = Modifier.size(7.dp),
                            shape = CircleShape,
                            color = LogiOnGreen2
                        ) {}
                    }

                    Spacer(Modifier.width(6.dp))

                    Text(
                        text = when {
                            isProcessing -> "서버에 저장하고 있습니다."
                            isCompleted -> "배송 완료 상태가 서버에 저장되었습니다."
                            checkedCount > 0 -> "상품 확인 상태가 서버에 저장되었습니다."
                            else -> "상품 구역을 확인해 주세요."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = LogiOnSubText
                    )
                }

                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

// 매장 연락, 길 안내, 이상 보고 공통 버튼
@Composable
private fun DetailActionButton(
    title: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    warning: Boolean = false,
    enabled: Boolean = true,
    onClick: () -> Unit = {}
) {
    val interactionSource = remember { MutableInteractionSource() }

    Card(
        modifier = modifier
            .height(48.dp)
            .clickable(
                enabled = enabled,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick
            ),
        shape = RoundedCornerShape(13.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (warning) LogiOnOrangeLight else LogiOnCard
        ),
        border = BorderStroke(
            1.dp,
            if (warning) Color(0xFFF4C6A0) else LogiOnBorder
        )
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 6.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            val contentColor = when {
                !enabled -> LogiOnSubText
                warning -> LogiOnOrange
                else -> LogiOnGreen2
            }

            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = contentColor,
                modifier = Modifier.size(17.dp)
            )
            Spacer(Modifier.width(4.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = if (!enabled) LogiOnSubText
                else if (warning) LogiOnOrange
                else LogiOnText
            )
        }
    }
}

// 상품 구역 확인 카드
@Composable
private fun ProductCheckCard(
    title: String,
    rightText: String,
    checked: Boolean,
    enabled: Boolean,
    onClick: () -> Unit
) {
    val interactionSource = remember { MutableInteractionSource() }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                enabled = enabled,
                interactionSource = interactionSource,
                indication = null,
                onClick = onClick
            ),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = LogiOnCard),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 9.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(31.dp),
                shape = CircleShape,
                color = if (checked) LogiOnGreen2 else Color.Transparent,
                border = if (checked) null else BorderStroke(1.dp, Color(0xFFC7D9D0))
            ) {
                if (checked) {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = null,
                            tint = Color.White,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }

            Spacer(Modifier.width(10.dp))

            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium,
                color = if (enabled || checked) LogiOnText else LogiOnSubText
            )

            Spacer(Modifier.weight(1f))

            Text(
                text = rightText,
                style = MaterialTheme.typography.bodySmall,
                color = if (checked) LogiOnGreen2 else LogiOnSubText
            )
        }
    }
}
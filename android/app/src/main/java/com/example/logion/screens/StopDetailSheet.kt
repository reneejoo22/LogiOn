package com.example.logion.screens

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
import androidx.compose.ui.unit.dp
import com.example.logion.model.DeliveryStop
import com.example.logion.ui.theme.*

// ==============================
// 배송지 상세 BottomSheet
// 배송지 정보와 상품 확인, 배송 완료 처리를 담당함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StopDetailSheet(
    stop: DeliveryStop,
    isCompleted: Boolean,
    checkedItems: Set<String>,
    onCheckedItemsChange: (Set<String>) -> Unit,
    onClose: () -> Unit,
    onComplete: () -> Unit,
    onCancelComplete: () -> Unit
) {
    val sheetState = rememberModalBottomSheetState(
        skipPartiallyExpanded = false
    )

    // 배송지별 상품 확인 상태
    val tobaccoChecked = checkedItems.contains("담배류")
    val drinkChecked = checkedItems.contains("상온 음료")
    val coldChecked = checkedItems.contains("냉장 상품")
    val foodChecked = checkedItems.contains("간편식")

    val checkedCount = checkedItems.size

    // 네 상품 구역을 모두 확인해야 배송 완료 가능
    val allChecked =
        tobaccoChecked &&
                drinkChecked &&
                coldChecked &&
                foodChecked

    ModalBottomSheet(
        onDismissRequest = onClose,
        sheetState = sheetState,
        containerColor = LogiOnBackground,
        dragHandle = {
            Surface(
                modifier = Modifier
                    .padding(
                        top = 8.dp,
                        bottom = 8.dp
                    )
                    .width(48.dp)
                    .height(4.dp),
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
                    .padding(
                        start = 16.dp,
                        end = 16.dp,
                        bottom = 18.dp
                    )
            ) {
                // 선택한 배송지의 기본 정보
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Top
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (isCompleted) {
                                "배송지 상세 · 배송 완료"
                            } else {
                                "배송지 상세 · ${stop.eta} 도착 예정"
                            },
                            style = MaterialTheme.typography.labelLarge,
                            color = LogiOnSubText
                        )

                        Spacer(modifier = Modifier.height(4.dp))

                        Text(
                            text = stop.name,
                            style = MaterialTheme.typography.headlineSmall,
                            color = LogiOnText
                        )

                        Spacer(modifier = Modifier.height(3.dp))

                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.LocationOn,
                                contentDescription = null,
                                tint = Color(0xFF96ABA1),
                                modifier = Modifier.size(15.dp)
                            )

                            Spacer(modifier = Modifier.width(4.dp))

                            Text(
                                text = stop.address,
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )
                        }
                    }

                    IconButton(
                        onClick = onClose,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "닫기",
                            tint = LogiOnGreen,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 배송 업무 중 자주 사용하는 빠른 기능
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(7.dp)
                ) {
                    DetailActionButton(
                        title = "매장 연락",
                        icon = Icons.Default.NotificationsNone,
                        modifier = Modifier.weight(1f)
                    )

                    DetailActionButton(
                        title = "길 안내",
                        icon = Icons.Default.LocationOn,
                        modifier = Modifier.weight(1f)
                    )

                    DetailActionButton(
                        title = "이상 보고",
                        icon = Icons.Default.WarningAmber,
                        modifier = Modifier.weight(1f),
                        warning = true
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                // 상품 확인 진행률
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(15.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = LogiOnGreenLight
                    ),
                    border = BorderStroke(
                        1.dp,
                        Color(0xFFD0E6DB)
                    )
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

                            Spacer(modifier = Modifier.weight(1f))

                            Text(
                                text = "$checkedCount / 4 구역 확인",
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        LinearProgressIndicator(
                            progress = { checkedCount / 4f },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(6.dp),
                            color = LogiOnGreen2,
                            trackColor = Color(0xFFD5E7DE)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // 상품을 선택하면 배송지별 체크 상태가 LogiOnApp에 저장됨
                ProductCheckCard(
                    title = "담배류",
                    rightText = if (tobaccoChecked) "확인" else "확인 필요",
                    checked = tobaccoChecked,
                    enabled = !isCompleted,
                    onClick = {
                        toggleItem(
                            item = "담배류",
                            checkedItems = checkedItems,
                            onCheckedItemsChange = onCheckedItemsChange
                        )
                    }
                )

                Spacer(modifier = Modifier.height(6.dp))

                ProductCheckCard(
                    title = "상온 음료",
                    rightText = if (drinkChecked) "확인" else "확인 필요",
                    checked = drinkChecked,
                    enabled = !isCompleted,
                    onClick = {
                        toggleItem(
                            item = "상온 음료",
                            checkedItems = checkedItems,
                            onCheckedItemsChange = onCheckedItemsChange
                        )
                    }
                )

                Spacer(modifier = Modifier.height(6.dp))

                ProductCheckCard(
                    title = "냉장 상품",
                    rightText = "4박스",
                    checked = coldChecked,
                    enabled = !isCompleted,
                    onClick = {
                        toggleItem(
                            item = "냉장 상품",
                            checkedItems = checkedItems,
                            onCheckedItemsChange = onCheckedItemsChange
                        )
                    }
                )

                Spacer(modifier = Modifier.height(6.dp))

                ProductCheckCard(
                    title = "간편식",
                    rightText = "3박스",
                    checked = foodChecked,
                    enabled = !isCompleted,
                    onClick = {
                        toggleItem(
                            item = "간편식",
                            checkedItems = checkedItems,
                            onCheckedItemsChange = onCheckedItemsChange
                        )
                    }
                )

                Spacer(modifier = Modifier.height(12.dp))

                // 미완료 배송은 모든 상품 확인 후 완료할 수 있고,
                // 이미 완료된 배송은 같은 버튼에서 완료 취소 가능
                Button(
                    onClick = {
                        if (isCompleted) {
                            onCancelComplete()
                        } else if (allChecked) {
                            onComplete()
                        }
                    },
                    enabled = isCompleted || allChecked,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(15.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (isCompleted) {
                            LogiOnOrange
                        } else {
                            LogiOnGreen
                        },
                        disabledContainerColor = Color(0xFFB8C9C2),
                        disabledContentColor = Color.White
                    )
                ) {
                    Icon(
                        imageVector = Icons.Default.Check,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp)
                    )

                    Spacer(modifier = Modifier.width(6.dp))

                    Text(
                        text = when {
                            isCompleted -> "배송 완료 취소"
                            allChecked -> "배송 완료 처리"
                            else -> "모든 상품을 확인해 주세요"
                        },
                        style = MaterialTheme.typography.titleMedium
                    )
                }

                Spacer(modifier = Modifier.height(8.dp))

                // 현재 작업 내용의 저장 상태 안내
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        modifier = Modifier.size(7.dp),
                        shape = CircleShape,
                        color = LogiOnGreen2
                    ) {}

                    Spacer(modifier = Modifier.width(6.dp))

                    Text(
                        text = when {
                            isCompleted ->
                                "배송 완료 상태가 기기에 저장되었습니다."

                            checkedCount > 0 ->
                                "상품 확인 내용이 임시 저장되었습니다."

                            else ->
                                "변경 내용은 오프라인 작업 큐에 저장됩니다."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = LogiOnSubText
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))
            }
        }
    }
}


private fun toggleItem(
    item: String,
    checkedItems: Set<String>,
    onCheckedItemsChange: (Set<String>) -> Unit
) {
    val newItems = if (checkedItems.contains(item)) {
        checkedItems - item
    } else {
        checkedItems + item
    }

    onCheckedItemsChange(newItems)
}


// 매장 연락, 길 안내, 이상 보고에 공통으로 사용하는 버튼
@Composable
private fun DetailActionButton(
    title: String,
    icon: ImageVector,
    modifier: Modifier = Modifier,
    warning: Boolean = false
) {
    Card(
        modifier = modifier.height(48.dp),
        shape = RoundedCornerShape(13.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (warning) {
                LogiOnOrangeLight
            } else {
                LogiOnCard
            }
        ),
        border = BorderStroke(
            1.dp,
            if (warning) {
                Color(0xFFF4C6A0)
            } else {
                LogiOnBorder
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 6.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (warning) {
                    LogiOnOrange
                } else {
                    LogiOnGreen2
                },
                modifier = Modifier.size(17.dp)
            )

            Spacer(modifier = Modifier.width(4.dp))

            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = if (warning) {
                    LogiOnOrange
                } else {
                    LogiOnText
                }
            )
        }
    }
}


// 확인 상태를 표시하고 변경하는 상품 카드
@Composable
private fun ProductCheckCard(
    title: String,
    rightText: String,
    checked: Boolean,
    enabled: Boolean,
    onClick: () -> Unit
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(
                enabled = enabled,
                interactionSource = interactionSource,
                indication = null
            ) {
                onClick()
            },
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = LogiOnCard
        ),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    horizontal = 12.dp,
                    vertical = 9.dp
                ),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Surface(
                modifier = Modifier.size(31.dp),
                shape = CircleShape,
                color = if (checked) {
                    LogiOnGreen2
                } else {
                    Color.Transparent
                },
                border = if (checked) {
                    null
                } else {
                    BorderStroke(
                        1.dp,
                        Color(0xFFC7D9D0)
                    )
                }
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

            Spacer(modifier = Modifier.width(10.dp))

            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium,
                color = LogiOnText
            )

            Spacer(modifier = Modifier.weight(1f))

            Text(
                text = rightText,
                style = MaterialTheme.typography.bodySmall,
                color = if (checked) {
                    LogiOnGreen2
                } else {
                    LogiOnSubText
                }
            )
        }
    }
}
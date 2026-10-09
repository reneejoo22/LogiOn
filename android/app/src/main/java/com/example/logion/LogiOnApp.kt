package com.example.logion

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import com.example.logion.model.DeliveryStop
import com.example.logion.screens.HomeScreen
import com.example.logion.screens.LogiOnBottomNavigation
import com.example.logion.screens.MoreScreen
import com.example.logion.screens.RouteScreen
import com.example.logion.screens.ScanScreen
import com.example.logion.screens.StopDetailSheet
import com.example.logion.screens.VoiceDock

// ==============================
// LogiOn 앱의 메인 화면 구성
// 화면 전환과 배송 상태, 상품 확인 상태를 관리함
// ==============================

@Composable
fun LogiOnApp() {
    // 현재 선택된 하단 메뉴를 저장
    var selectedTab by remember {
        mutableStateOf("home")
    }

    // 사용자가 선택해서 열어둔 배송지 상세 정보
    var selectedStop by remember {
        mutableStateOf<DeliveryStop?>(null)
    }

    // 완료된 배송지의 id를 저장
    var completedStops by remember {
        mutableStateOf(setOf<Int>())
    }

    // 배송지별 상품 체크 상태를 저장
    var checkedItemsByStop by remember {
        mutableStateOf<Map<Int, Set<String>>>(emptyMap())
    }

    // 하단 음성 입력 버튼의 현재 상태
    var isListening by remember {
        mutableStateOf(false)
    }

    // 한 배송지에서 확인해야 하는 전체 상품 구역
    val allItems = setOf(
        "담배류",
        "상온 음료",
        "냉장 상품",
        "간편식"
    )

    Scaffold(
        // 모든 화면에서 공통으로 사용하는 음성 입력창과 하단 네비게이션
        bottomBar = {
            Column {
                VoiceDock(
                    isListening = isListening,
                    onVoiceClick = {
                        isListening = !isListening
                    }
                )

                LogiOnBottomNavigation(
                    selectedTab = selectedTab,
                    onTabSelected = { tab ->
                        selectedTab = tab
                    }
                )
            }
        }
    ) { paddingValues ->
        Box(
            modifier = Modifier.padding(paddingValues)
        ) {
            // 선택된 하단 탭에 맞는 화면 표시
            when (selectedTab) {
                "home" -> {
                    HomeScreen(
                        completedStops = completedStops,
                        isListening = isListening,
                        onStopClick = { stop ->
                            selectedStop = stop
                        }
                    )
                }

                "route" -> {
                    RouteScreen(
                        completedStops = completedStops,
                        onStopClick = { stop ->
                            selectedStop = stop
                        },

                        // 배송목록의 빠른 체크 버튼으로 완료/완료 취소 처리
                        onQuickToggleComplete = { stop ->
                            val alreadyCompleted =
                                completedStops.contains(stop.id)

                            if (alreadyCompleted) {
                                completedStops =
                                    completedStops - stop.id
                            } else {
                                completedStops =
                                    completedStops + stop.id

                                checkedItemsByStop =
                                    checkedItemsByStop + (
                                            stop.id to allItems
                                            )
                            }
                        }
                    )
                }

                "scan" -> ScanScreen()
                "more" -> MoreScreen()
            }

            // 배송지를 선택했을 때 화면 위에 상세 BottomSheet 표시
            selectedStop?.let { stop ->
                val isCompleted =
                    completedStops.contains(stop.id)

                val checkedItems =
                    checkedItemsByStop[stop.id] ?: emptySet()

                StopDetailSheet(
                    stop = stop,
                    isCompleted = isCompleted,
                    checkedItems = checkedItems,

                    // 상품을 체크하거나 해제할 때 배송지별 상태를 저장
                    onCheckedItemsChange = { newItems ->
                        checkedItemsByStop =
                            checkedItemsByStop + (
                                    stop.id to newItems
                                    )
                    },

                    onClose = {
                        selectedStop = null
                    },

                    // 상세 화면에서 배송 완료 처리
                    onComplete = {
                        completedStops =
                            completedStops + stop.id

                        checkedItemsByStop =
                            checkedItemsByStop + (
                                    stop.id to allItems
                                    )

                        selectedStop = null
                    },

                    // 완료된 배송지를 다시 미완료 상태로 변경
                    onCancelComplete = {
                        completedStops = completedStops - stop.id
                        // 취소 시 상품 확인 상태도 초기화
                        checkedItemsByStop = checkedItemsByStop - stop.id

                        selectedStop = null
                    }
                )
            }
        }
    }
}
package com.example.logion

import android.util.Log
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.example.logion.data.remote.CompleteRequest
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.data.remote.StopDetailResponse
import com.example.logion.data.remote.ZoneCheckRequest
import com.example.logion.model.DeliveryStop
import com.example.logion.screens.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

// ==============================
// LogiOn 앱 메인
// 화면 전환, 배송 데이터, 서버 오류 상태를 관리함
// ==============================

@Composable
fun LogiOnApp() {
    var selectedTab by remember { mutableStateOf("home") }
    var scanPage by remember { mutableStateOf("main") }
    var issueStopId by remember { mutableStateOf<Int?>(null) }

    var selectedStop by remember { mutableStateOf<DeliveryStop?>(null) }
    var selectedStopDetail by remember { mutableStateOf<StopDetailResponse?>(null) }

    var stops by remember { mutableStateOf<List<DeliveryStop>>(emptyList()) }
    var completedStops by remember { mutableStateOf(setOf<Int>()) }
    var departAt by remember { mutableStateOf<String?>(null) }
    var estEndAt by remember { mutableStateOf<String?>(null) }

    var isListening by remember { mutableStateOf(false) }
    var processingStopIds by remember { mutableStateOf(setOf<Int>()) }

    val coroutineScope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    fun showMessage(message: String) {
        coroutineScope.launch {
            snackbarHostState.showSnackbar(message, withDismissAction = true)
        }
    }

    // 같은 배송지 API 중복 호출 방지
    fun beginProcessing(stopId: Int): Boolean {
        if (stopId in processingStopIds) return false
        processingStopIds = processingStopIds + stopId
        return true
    }

    fun endProcessing(stopId: Int) {
        processingStopIds = processingStopIds - stopId
    }

    // 오늘 배송 정보 새로고침
    suspend fun refreshTodayRoute() {
        try {
            val route = RetrofitClient.api.getTodayRoute()

            departAt = route.departAt
            estEndAt = route.estEndAt

            stops = route.stops.map { remoteStop ->
                DeliveryStop(
                    id = remoteStop.id,
                    name = remoteStop.store.name,
                    address = remoteStop.store.address,
                    eta = formatEta(remoteStop.eta),
                    status = when {
                        remoteStop.status == "done" -> "완료"
                        remoteStop.isNext -> "다음 배송"
                        else -> "예정"
                    },
                    boxes = remoteStop.boxes,
                    distance = remoteStop.distanceKm?.let { "$it km" } ?: "-",
                    notice = remoteStop.notice,
                    lat = remoteStop.store.lat,
                    lng = remoteStop.store.lng
                )
            }

            completedStops = route.stops
                .filter { it.status == "done" }
                .map { it.id }
                .toSet()

            if (route.stops.isEmpty()) showMessage("오늘 예정된 배송이 없습니다.")

            Log.d(
                "API_ROUTE",
                "배송 상태 새로고침 완료: ${route.summary.done}/${route.summary.total}"
            )
        } catch (e: Exception) {
            Log.e("API_ROUTE", "오늘 배송 불러오기 실패", e)
            showMessage(
                apiErrorMessage(e, "오늘 배송 정보를 불러오지 못했습니다.")
            )
        }
    }

    // 배송지 상세 조회
    fun openStopDetail(stop: DeliveryStop) {
        coroutineScope.launch {
            if (!beginProcessing(stop.id)) return@launch

            try {
                selectedStopDetail = RetrofitClient.api.getStopDetail(stop.id)
                selectedStop = stop
                Log.d("API_DETAIL", "배송지 상세 조회 성공: ${stop.name}")
            } catch (e: Exception) {
                Log.e("API_DETAIL", "배송지 상세 조회 실패: ${stop.name}", e)
                showMessage(
                    apiErrorMessage(e, "배송지 정보를 불러오지 못했습니다.")
                )
            } finally {
                endProcessing(stop.id)
            }
        }
    }

    LaunchedEffect(Unit) {
        refreshTodayRoute()
    }

    Scaffold(
        snackbarHost = {
            SnackbarHost(hostState = snackbarHostState)
        },
        bottomBar = {
            Column {
                VoiceDock(
                    isListening = isListening,
                    onVoiceClick = { isListening = !isListening }
                )

                LogiOnBottomNavigation(
                    selectedTab = selectedTab,
                    onTabSelected = { tab ->
                        selectedTab = tab

                        if (tab != "scan") {
                            scanPage = "main"
                            issueStopId = null
                        }
                    }
                )
            }
        }
    ) { paddingValues ->
        Box(modifier = Modifier.padding(paddingValues)) {
            when (selectedTab) {
                "home" -> {
                    HomeScreen(
                        stops = stops,
                        completedStops = completedStops,
                        departAt = departAt,
                        estEndAt = estEndAt,
                        isListening = isListening,
                        onStopClick = ::openStopDetail
                    )
                }

                "route" -> {
                    RouteScreen(
                        stops = stops,
                        completedStops = completedStops,
                        onStopClick = ::openStopDetail,
                        onQuickToggleComplete = { stop ->
                            coroutineScope.launch {
                                if (!beginProcessing(stop.id)) return@launch

                                try {
                                    if (stop.id in completedStops) {
                                        RetrofitClient.api.cancelComplete(stop.id)
                                        Log.d(
                                            "API_COMPLETE",
                                            "배송 완료 취소 성공: ${stop.name}"
                                        )
                                    } else {
                                        RetrofitClient.api.completeStop(
                                            stopId = stop.id,
                                            body = CompleteRequest()
                                        )
                                        Log.d(
                                            "API_COMPLETE",
                                            "배송 완료 성공: ${stop.name}"
                                        )
                                    }

                                    refreshTodayRoute()
                                } catch (e: Exception) {
                                    Log.e("API_COMPLETE", "배송 상태 변경 실패", e)
                                    showMessage(
                                        apiErrorMessage(
                                            e,
                                            "배송 상태를 변경하지 못했습니다."
                                        )
                                    )
                                } finally {
                                    endProcessing(stop.id)
                                }
                            }
                        }
                    )
                }

                "scan" -> {
                    when (scanPage) {
                        "camera" -> {
                            CameraScanScreen(
                                onBack = { scanPage = "main" }
                            )
                        }

                        "manual" -> {
                            ManualBarcodeScreen(
                                onBack = { scanPage = "main" }
                            )
                        }

                        "issue" -> {
                            IssueReportScreen(
                                stops = stops,
                                initialStopId = issueStopId,
                                onBack = {
                                    scanPage = "main"
                                    issueStopId = null
                                }
                            )
                        }

                        else -> {
                            ScanScreen(
                                onCameraScanClick = { scanPage = "camera" },
                                onManualInputClick = { scanPage = "manual" },
                                onIssueReportClick = {
                                    issueStopId = null
                                    scanPage = "issue"
                                }
                            )
                        }
                    }
                }

                // ai 채팅
                "chat" -> ChatScreen(
                    // 음성/채팅으로 완료·이상 보고를 하면 운행 목록을 다시 불러옴
                    onRouteChanged = {
                        coroutineScope.launch { refreshTodayRoute() }
                    },
                    onOpenScanner = {
                        selectedTab = "scan"
                        scanPage = "camera"
                    }
                )

                "more" -> MoreScreen()
            }

            val stop = selectedStop
            val detail = selectedStopDetail

            if (stop != null && detail != null) {
                val isProcessing = stop.id in processingStopIds

                StopDetailSheet(
                    stop = stop,
                    detail = detail,
                    isProcessing = isProcessing,

                    onZoneToggle = { zone ->
                        coroutineScope.launch {
                            if (!beginProcessing(stop.id)) return@launch

                            try {
                                selectedStopDetail = RetrofitClient.api.setZoneChecked(
                                    stopId = stop.id,
                                    category = zone.category,
                                    body = ZoneCheckRequest(checked = !zone.checked)
                                )

                                Log.d(
                                    "API_ZONE",
                                    "${zone.label} 체크 변경 성공"
                                )
                            } catch (e: Exception) {
                                Log.e(
                                    "API_ZONE",
                                    "${zone.label} 체크 변경 실패",
                                    e
                                )

                                showMessage(
                                    apiErrorMessage(
                                        e,
                                        "상품 확인 상태를 저장하지 못했습니다."
                                    )
                                )
                            } finally {
                                endProcessing(stop.id)
                            }
                        }
                    },

                    onClose = {
                        if (!isProcessing) {
                            selectedStop = null
                            selectedStopDetail = null
                        }
                    },

                    onComplete = {
                        coroutineScope.launch {
                            if (!beginProcessing(stop.id)) return@launch

                            try {
                                RetrofitClient.api.completeStop(
                                    stopId = stop.id,
                                    body = CompleteRequest()
                                )

                                refreshTodayRoute()
                                selectedStop = null
                                selectedStopDetail = null

                                Log.d(
                                    "API_COMPLETE",
                                    "배송 완료 성공: ${stop.name}"
                                )
                            } catch (e: Exception) {
                                Log.e("API_COMPLETE", "배송 완료 실패", e)

                                showMessage(
                                    apiErrorMessage(
                                        e,
                                        "배송 완료 처리에 실패했습니다."
                                    )
                                )
                            } finally {
                                endProcessing(stop.id)
                            }
                        }
                    },

                    onCancelComplete = {
                        coroutineScope.launch {
                            if (!beginProcessing(stop.id)) return@launch

                            try {
                                RetrofitClient.api.cancelComplete(stop.id)

                                refreshTodayRoute()
                                selectedStop = null
                                selectedStopDetail = null

                                Log.d(
                                    "API_COMPLETE",
                                    "배송 완료 취소 성공: ${stop.name}"
                                )
                            } catch (e: Exception) {
                                Log.e(
                                    "API_COMPLETE",
                                    "배송 완료 취소 실패",
                                    e
                                )

                                showMessage(
                                    apiErrorMessage(
                                        e,
                                        "배송 완료 취소에 실패했습니다."
                                    )
                                )
                            } finally {
                                endProcessing(stop.id)
                            }
                        }
                    },

                    onIssueReport = {
                        if (!isProcessing) {
                            issueStopId = stop.id
                            selectedStop = null
                            selectedStopDetail = null
                            selectedTab = "scan"
                            scanPage = "issue"
                        }
                    }
                )
            }
        }
    }
}

// 백엔드 날짜+시간에서 HH:mm만 표시
private fun formatEta(eta: String): String =
    eta.substringAfter("T", eta).take(5)

// 서버 오류 -> 사용자용 문구
private fun apiErrorMessage(
    exception: Exception,
    defaultMessage: String
): String = when (exception) {
    is IOException -> "서버에 연결할 수 없습니다."

    is HttpException -> when (exception.code()) {
        404 -> "요청한 정보를 찾을 수 없습니다."
        408 -> "서버 응답이 지연되고 있습니다."
        500, 502, 503 -> "서버에 문제가 발생했습니다."
        else -> defaultMessage
    }

    else -> defaultMessage
}
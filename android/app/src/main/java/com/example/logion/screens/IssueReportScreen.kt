package com.example.logion.screens

import android.util.Log
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.example.logion.data.remote.IssueCreateRequest
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.data.remote.StopItemResponse
import com.example.logion.model.DeliveryStop
import com.example.logion.ui.theme.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

// ==============================
// 이상 보고 화면
// 배송 중 발생한 상품 문제를 서버에 등록함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun IssueReportScreen(
    stops: List<DeliveryStop>,
    initialStopId: Int? = null,
    onBack: () -> Unit
) {
    val issueTypes = listOf(
        "파손",
        "수량 부족",
        "오배송",
        "온도이상"
    )

    val units = listOf(
        "개",
        "박스",
        "판",
        "봉지"
    )

    // 상세 화면에서 들어온 경우 해당 배송지를 자동 선택
    var selectedStopId by remember(initialStopId, stops) {
        mutableStateOf(
            initialStopId ?: stops.firstOrNull()?.id
        )
    }

    var selectedIssueType by remember {
        mutableStateOf("")
    }

    var items by remember {
        mutableStateOf<List<StopItemResponse>>(emptyList())
    }

    var selectedProductId by remember {
        mutableStateOf<Int?>(null)
    }

    var quantity by remember {
        mutableStateOf("")
    }

    var selectedUnit by remember {
        mutableStateOf("개")
    }

    var stopMenuExpanded by remember {
        mutableStateOf(false)
    }

    var productMenuExpanded by remember {
        mutableStateOf(false)
    }

    var unitMenuExpanded by remember {
        mutableStateOf(false)
    }

    var isLoadingItems by remember {
        mutableStateOf(false)
    }

    var isSubmitting by remember {
        mutableStateOf(false)
    }

    var errorMessage by remember {
        mutableStateOf<String?>(null)
    }

    var successMessage by remember {
        mutableStateOf<String?>(null)
    }

    val coroutineScope = rememberCoroutineScope()

    val selectedStop = stops.firstOrNull {
        it.id == selectedStopId
    }

    val selectedProduct = items.firstOrNull {
        it.productId == selectedProductId
    }

    // 선택한 배송지의 실제 상품 목록을 서버에서 조회
    LaunchedEffect(selectedStopId) {
        val stopId = selectedStopId ?: return@LaunchedEffect

        isLoadingItems = true
        selectedProductId = null

        try {
            val detail = RetrofitClient.api.getStopDetail(stopId)
            items = detail.items
        } catch (e: Exception) {
            items = emptyList()
            Log.e("API_ISSUE", "배송지 상품 조회 실패", e)
        } finally {
            isLoadingItems = false
        }
    }

    // 이상 보고를 서버 DB에 등록
    fun submitIssue() {
        val stopId = selectedStopId

        if (stopId == null) {
            errorMessage = "배송지를 선택해 주세요."
            return
        }

        if (selectedIssueType.isBlank()) {
            errorMessage = "문제 유형을 선택해 주세요."
            return
        }

        val qty = if (quantity.isBlank()) {
            null
        } else {
            quantity.toIntOrNull()
        }

        if (quantity.isNotBlank() && (qty == null || qty <= 0)) {
            errorMessage = "수량을 올바르게 입력해 주세요."
            return
        }

        val apiType = if (selectedIssueType == "수량 부족") {
            "수량부족"
        } else {
            selectedIssueType
        }

        coroutineScope.launch {
            isSubmitting = true
            errorMessage = null
            successMessage = null

            try {
                RetrofitClient.api.createIssue(
                    stopId = stopId,
                    body = IssueCreateRequest(
                        type = apiType,
                        productId = selectedProductId,
                        qty = qty,
                        unit = if (qty != null) selectedUnit else null,
                        source = "touch"
                    )
                )

                successMessage = "이상 보고가 등록되었습니다."

                Log.d(
                    "API_ISSUE",
                    "이상 보고 등록 성공: $apiType"
                )

                selectedIssueType = ""
                selectedProductId = null
                quantity = ""
                selectedUnit = "개"
            } catch (e: HttpException) {
                errorMessage = when (e.code()) {
                    404 -> "배송지 또는 상품 정보를 찾을 수 없습니다."
                    422 -> "입력한 내용을 다시 확인해 주세요."
                    else -> "이상 보고 등록에 실패했습니다."
                }

                Log.e("API_ISSUE", "이상 보고 등록 실패", e)
            } catch (e: Exception) {
                errorMessage = "서버에 연결할 수 없습니다."
                Log.e("API_ISSUE", "이상 보고 등록 중 오류", e)
            } finally {
                isSubmitting = false
            }
        }
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
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(
                        start = 22.dp,
                        end = 22.dp,
                        top = 14.dp,
                        bottom = 18.dp
                    )
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = onBack,
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "뒤로가기",
                            tint = LogiOnGreen
                        )
                    }

                    Spacer(Modifier.width(4.dp))

                    Text(
                        text = "이상 보고",
                        style = MaterialTheme.typography.headlineSmall,
                        color = LogiOnText
                    )
                }

                Spacer(Modifier.height(8.dp))

                Text(
                    text = "배송 중 발견한 상품 문제를 등록하세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(18.dp))

                Text(
                    text = "배송지",
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(7.dp))

                Box {
                    SelectionCard(
                        text = selectedStop?.name ?: "배송지를 선택하세요",
                        onClick = {
                            stopMenuExpanded = true
                        }
                    )

                    DropdownMenu(
                        expanded = stopMenuExpanded,
                        onDismissRequest = {
                            stopMenuExpanded = false
                        }
                    ) {
                        stops.forEach { stop ->
                            DropdownMenuItem(
                                text = {
                                    Text(stop.name)
                                },
                                onClick = {
                                    selectedStopId = stop.id
                                    stopMenuExpanded = false
                                    errorMessage = null
                                    successMessage = null
                                }
                            )
                        }
                    }
                }

                Spacer(Modifier.height(17.dp))

                Text(
                    text = "문제 유형",
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(7.dp))

                Column(
                    verticalArrangement = Arrangement.spacedBy(7.dp)
                ) {
                    issueTypes.chunked(2).forEach { rowTypes ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(7.dp)
                        ) {
                            rowTypes.forEach { type ->
                                FilterChip(
                                    selected = selectedIssueType == type,
                                    onClick = {
                                        selectedIssueType = type
                                        errorMessage = null
                                        successMessage = null
                                    },
                                    label = {
                                        Text(type)
                                    },
                                    leadingIcon = if (
                                        selectedIssueType == type
                                    ) {
                                        {
                                            Icon(
                                                imageVector = Icons.Default.CheckCircle,
                                                contentDescription = null,
                                                modifier = Modifier.size(17.dp)
                                            )
                                        }
                                    } else {
                                        null
                                    },
                                    modifier = Modifier.weight(1f),
                                    colors = FilterChipDefaults.filterChipColors(
                                        selectedContainerColor = LogiOnOrangeLight,
                                        selectedLabelColor = LogiOnOrange,
                                        selectedLeadingIconColor = LogiOnOrange
                                    )
                                )
                            }
                        }
                    }
                }

                Spacer(Modifier.height(17.dp))

                Text(
                    text = "상품",
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(3.dp))

                Text(
                    text = "특정 상품 문제라면 선택하세요. 선택하지 않아도 등록할 수 있습니다.",
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(7.dp))

                Box {
                    SelectionCard(
                        text = when {
                            isLoadingItems -> "상품 불러오는 중..."
                            selectedProduct != null -> selectedProduct.name
                            else -> "상품 지정 안 함"
                        },
                        enabled = !isLoadingItems,
                        onClick = {
                            productMenuExpanded = true
                        }
                    )

                    DropdownMenu(
                        expanded = productMenuExpanded,
                        onDismissRequest = {
                            productMenuExpanded = false
                        }
                    ) {
                        DropdownMenuItem(
                            text = {
                                Text("상품 지정 안 함")
                            },
                            onClick = {
                                selectedProductId = null
                                productMenuExpanded = false
                            }
                        )

                        items.forEach { item ->
                            DropdownMenuItem(
                                text = {
                                    Text(
                                        "${item.name} · ${item.qty}${item.unit}"
                                    )
                                },
                                onClick = {
                                    selectedProductId = item.productId
                                    productMenuExpanded = false
                                }
                            )
                        }
                    }
                }

                Spacer(Modifier.height(17.dp))

                Text(
                    text = "수량",
                    style = MaterialTheme.typography.titleMedium,
                    color = LogiOnText
                )

                Spacer(Modifier.height(3.dp))

                Text(
                    text = "필요한 경우에만 입력하세요.",
                    style = MaterialTheme.typography.bodySmall,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(7.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = quantity,
                        onValueChange = { value ->
                            quantity = value.filter { it.isDigit() }
                            errorMessage = null
                            successMessage = null
                        },
                        modifier = Modifier.weight(1f),
                        placeholder = {
                            Text("수량")
                        },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Number
                        ),
                        shape = RoundedCornerShape(14.dp)
                    )

                    Box(
                        modifier = Modifier.width(110.dp)
                    ) {
                        SelectionCard(
                            text = selectedUnit,
                            onClick = {
                                unitMenuExpanded = true
                            }
                        )

                        DropdownMenu(
                            expanded = unitMenuExpanded,
                            onDismissRequest = {
                                unitMenuExpanded = false
                            }
                        ) {
                            units.forEach { unit ->
                                DropdownMenuItem(
                                    text = {
                                        Text(unit)
                                    },
                                    onClick = {
                                        selectedUnit = unit
                                        unitMenuExpanded = false
                                    }
                                )
                            }
                        }
                    }
                }

                errorMessage?.let { message ->
                    Spacer(Modifier.height(12.dp))
                    MessageCard(
                        text = message,
                        success = false
                    )
                }

                successMessage?.let { message ->
                    Spacer(Modifier.height(12.dp))
                    MessageCard(
                        text = message,
                        success = true
                    )
                }

                Spacer(Modifier.height(18.dp))

                Button(
                    onClick = {
                        submitIssue()
                    },
                    enabled = !isSubmitting,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    shape = RoundedCornerShape(15.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = LogiOnOrange
                    )
                ) {
                    if (isSubmitting) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(19.dp),
                            strokeWidth = 2.dp,
                            color = Color.White
                        )
                    } else {
                        Icon(
                            imageVector = Icons.Default.WarningAmber,
                            contentDescription = null,
                            modifier = Modifier.size(19.dp)
                        )

                        Spacer(Modifier.width(7.dp))

                        Text(
                            text = "이상 보고 등록",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

// 배송지, 상품, 단위 선택 공통 카드
@Composable
private fun SelectionCard(
    text: String,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    val interactionSource = remember {
        MutableInteractionSource()
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(52.dp)
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
        border = BorderStroke(
            1.dp,
            LogiOnBorder
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 13.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = text,
                style = MaterialTheme.typography.bodyMedium,
                color = if (enabled) LogiOnText else LogiOnSubText,
                modifier = Modifier.weight(1f)
            )

            Icon(
                imageVector = Icons.Default.KeyboardArrowDown,
                contentDescription = null,
                tint = LogiOnSubText,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

// 성공 또는 오류 메시지
@Composable
private fun MessageCard(
    text: String,
    success: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (success) {
                LogiOnGreenLight
            } else {
                LogiOnOrangeLight
            }
        ),
        border = BorderStroke(
            1.dp,
            if (success) {
                Color(0xFFC7E1D5)
            } else {
                Color(0xFFF3C9A8)
            }
        )
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(13.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = if (success) {
                LogiOnGreen2
            } else {
                LogiOnOrange
            }
        )
    }
}
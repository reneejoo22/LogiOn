package com.example.logion.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.example.logion.data.remote.BarcodeProductResponse
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.ui.theme.*
import kotlinx.coroutines.launch
import retrofit2.HttpException

// ==============================
// 바코드 수기 입력 화면
// 직접 입력한 바코드 번호로 상품과 배송 정보를 조회함
// ==============================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ManualBarcodeScreen(
    onBack: () -> Unit
) {
    var barcode by remember { mutableStateOf("") }
    var product by remember {
        mutableStateOf<BarcodeProductResponse?>(null)
    }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    val coroutineScope = rememberCoroutineScope()

    // 입력한 바코드를 백엔드에서 조회
    fun searchBarcode() {
        val value = barcode.trim()

        if (value.isEmpty()) {
            errorMessage = "바코드 번호를 입력해 주세요."
            product = null
            return
        }

        coroutineScope.launch {
            isLoading = true
            errorMessage = null
            product = null

            try {
                product = RetrofitClient.api.getProductByBarcode(value)
            } catch (e: HttpException) {
                errorMessage = if (e.code() == 404) {
                    "등록되지 않은 바코드입니다."
                } else {
                    "상품 정보를 불러오지 못했습니다."
                }
            } catch (e: Exception) {
                errorMessage = "서버에 연결할 수 없습니다."
            } finally {
                isLoading = false
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
                // 스캔 화면으로 돌아가기
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
                        text = "수기 입력",
                        style = MaterialTheme.typography.headlineSmall,
                        color = LogiOnText
                    )
                }

                Spacer(Modifier.height(8.dp))

                Text(
                    text = "바코드가 인식되지 않을 때 번호를 직접 입력하세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(16.dp))

                // 바코드 번호 입력
                OutlinedTextField(
                    value = barcode,
                    onValueChange = {
                        barcode = it.filter { char ->
                            char.isDigit()
                        }
                        errorMessage = null
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = {
                        Text("바코드 번호")
                    },
                    placeholder = {
                        Text("13자리 바코드 입력")
                    },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction = ImeAction.Search
                    ),
                    keyboardActions = KeyboardActions(
                        onSearch = {
                            searchBarcode()
                        }
                    ),
                    shape = RoundedCornerShape(14.dp)
                )

                Spacer(Modifier.height(10.dp))

                Button(
                    onClick = {
                        searchBarcode()
                    },
                    enabled = !isLoading,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = LogiOnGreen2
                    )
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(19.dp),
                            strokeWidth = 2.dp,
                            color = Color.White
                        )
                    } else {
                        Icon(
                            imageVector = Icons.Default.Search,
                            contentDescription = null,
                            modifier = Modifier.size(19.dp)
                        )

                        Spacer(Modifier.width(7.dp))

                        Text(
                            text = "상품 조회",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }

                // 조회 실패 안내
                errorMessage?.let { message ->
                    Spacer(Modifier.height(12.dp))

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = LogiOnOrangeLight
                        ),
                        border = BorderStroke(
                            1.dp,
                            Color(0xFFF3C9A8)
                        )
                    ) {
                        Text(
                            text = message,
                            modifier = Modifier.padding(13.dp),
                            style = MaterialTheme.typography.bodyMedium,
                            color = LogiOnOrange
                        )
                    }
                }

                // 조회한 상품 정보
                product?.let { result ->
                    Spacer(Modifier.height(16.dp))

                    Text(
                        text = "조회 결과",
                        style = MaterialTheme.typography.titleMedium,
                        color = LogiOnText
                    )

                    Spacer(Modifier.height(8.dp))

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(17.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = LogiOnCard
                        ),
                        border = BorderStroke(
                            1.dp,
                            LogiOnBorder
                        )
                    ) {
                        Column(
                            modifier = Modifier.padding(15.dp)
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Surface(
                                    modifier = Modifier.size(40.dp),
                                    shape = RoundedCornerShape(11.dp),
                                    color = LogiOnGreenLight
                                ) {
                                    Box(
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.Inventory2,
                                            contentDescription = null,
                                            tint = LogiOnGreen2,
                                            modifier = Modifier.size(21.dp)
                                        )
                                    }
                                }

                                Spacer(Modifier.width(11.dp))

                                Column {
                                    Text(
                                        text = result.name,
                                        style = MaterialTheme.typography.titleLarge,
                                        color = LogiOnText
                                    )

                                    Spacer(Modifier.height(2.dp))

                                    Text(
                                        text = result.categoryLabel,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }
                            }

                            Spacer(Modifier.height(12.dp))
                            HorizontalDivider(color = LogiOnBorder)
                            Spacer(Modifier.height(10.dp))

                            Text(
                                text = "바코드 ${result.barcode}",
                                style = MaterialTheme.typography.bodySmall,
                                color = LogiOnSubText
                            )

                            Spacer(Modifier.height(12.dp))

                            Text(
                                text = "오늘 배송",
                                style = MaterialTheme.typography.titleMedium,
                                color = LogiOnText
                            )

                            Spacer(Modifier.height(7.dp))

                            if (result.deliveries.isEmpty()) {
                                Text(
                                    text = "오늘 배송 예정이 없습니다.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = LogiOnSubText
                                )
                            } else {
                                result.deliveries.forEachIndexed { index, delivery ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(
                                            modifier = Modifier.weight(1f)
                                        ) {
                                            Text(
                                                text = delivery.storeName,
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = LogiOnText
                                            )

                                            Text(
                                                text = if (delivery.status == "done") {
                                                    "배송 완료"
                                                } else {
                                                    "배송 예정"
                                                },
                                                style = MaterialTheme.typography.bodySmall,
                                                color = LogiOnSubText
                                            )
                                        }

                                        Text(
                                            text = "${delivery.qty}${delivery.unit}",
                                            style = MaterialTheme.typography.titleMedium,
                                            color = LogiOnGreen2
                                        )
                                    }

                                    if (index < result.deliveries.lastIndex) {
                                        Spacer(Modifier.height(7.dp))
                                        HorizontalDivider(
                                            color = LogiOnBorder
                                        )
                                        Spacer(Modifier.height(7.dp))
                                    }
                                }
                            }
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))
            }
        }
    }
}
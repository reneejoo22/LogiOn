package com.example.logion.screens

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.LocalOverscrollFactory
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.logion.data.remote.BarcodeProductResponse
import com.example.logion.data.remote.RetrofitClient
import com.example.logion.ui.theme.*
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

// ==============================
// 카메라 바코드 스캔 화면
// CameraX와 ML Kit으로 바코드를 읽고 상품 정보를 조회함
// ==============================

@OptIn(ExperimentalMaterial3Api::class, ExperimentalGetImage::class)
@Composable
fun CameraScanScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val coroutineScope = rememberCoroutineScope()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
        )
    }

    var permissionDenied by remember { mutableStateOf(false) }
    var detectedBarcode by remember { mutableStateOf<String?>(null) }
    var product by remember { mutableStateOf<BarcodeProductResponse?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var cameraErrorMessage by remember { mutableStateOf<String?>(null) }
    var scanSession by remember { mutableIntStateOf(0) }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
        permissionDenied = !granted

        if (granted) {
            cameraErrorMessage = null
            scanSession++
        }
    }

    // 화면 진입 시 카메라 권한 요청
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    // 앱 설정에서 돌아온 경우 권한 상태 다시 확인
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                val granted = ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.CAMERA
                ) == PackageManager.PERMISSION_GRANTED

                if (granted && !hasCameraPermission) {
                    hasCameraPermission = true
                    permissionDenied = false
                    cameraErrorMessage = null
                    scanSession++
                } else {
                    hasCameraPermission = granted
                }
            }
        }

        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // 인식한 바코드로 상품 조회
    fun searchProduct(barcode: String) {
        if (isLoading) return

        coroutineScope.launch {
            isLoading = true
            errorMessage = null
            product = null

            try {
                product = RetrofitClient.api.getProductByBarcode(barcode)
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
                    .padding(start = 22.dp, end = 22.dp, top = 14.dp, bottom = 18.dp)
            ) {
                // 상단 제목
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack, modifier = Modifier.size(36.dp)) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "뒤로가기",
                            tint = LogiOnGreen
                        )
                    }

                    Spacer(Modifier.width(4.dp))

                    Text(
                        text = "카메라 스캔",
                        style = MaterialTheme.typography.headlineSmall,
                        color = LogiOnText
                    )
                }

                Spacer(Modifier.height(7.dp))

                Text(
                    text = "상품 바코드를 프레임 안에 맞춰주세요.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LogiOnSubText
                )

                Spacer(Modifier.height(14.dp))

                when {
                    // 카메라 권한 없음
                    !hasCameraPermission -> {
                        CameraPermissionCard(
                            denied = permissionDenied,
                            onRequestPermission = {
                                permissionLauncher.launch(Manifest.permission.CAMERA)
                            },
                            onOpenSettings = {
                                val intent = Intent(
                                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                    Uri.parse("package:${context.packageName}")
                                )
                                context.startActivity(intent)
                            }
                        )
                    }

                    // 카메라 실행 실패
                    cameraErrorMessage != null -> {
                        CameraErrorCard(
                            message = cameraErrorMessage ?: "카메라를 시작하지 못했습니다.",
                            onRetry = {
                                cameraErrorMessage = null
                                detectedBarcode = null
                                product = null
                                errorMessage = null
                                scanSession++
                            }
                        )
                    }

                    // 카메라 실행
                    detectedBarcode == null -> {
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(310.dp),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.Black)
                        ) {
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center
                            ) {
                                BarcodeCameraPreview(
                                    scanSession = scanSession,
                                    onBarcodeDetected = { barcode ->
                                        if (detectedBarcode == null) {
                                            detectedBarcode = barcode
                                            searchProduct(barcode)
                                        }
                                    },
                                    onCameraError = { cameraErrorMessage = it }
                                )

                                Surface(
                                    modifier = Modifier
                                        .fillMaxWidth(0.78f)
                                        .height(145.dp),
                                    shape = RoundedCornerShape(18.dp),
                                    color = Color.Transparent,
                                    border = BorderStroke(2.dp, Color.White)
                                ) {}

                                Surface(
                                    modifier = Modifier
                                        .align(Alignment.BottomCenter)
                                        .padding(bottom = 15.dp),
                                    shape = RoundedCornerShape(20.dp),
                                    color = Color.Black.copy(alpha = 0.55f)
                                ) {
                                    Text(
                                        text = "바코드를 자동으로 인식합니다",
                                        modifier = Modifier.padding(
                                            horizontal = 12.dp,
                                            vertical = 6.dp
                                        ),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = Color.White
                                    )
                                }
                            }
                        }
                    }

                    // 바코드 인식 완료
                    else -> {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(17.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = LogiOnGreenLight
                            ),
                            border = BorderStroke(1.dp, Color(0xFFCBE3D7))
                        ) {
                            Row(
                                modifier = Modifier.padding(14.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Surface(
                                    modifier = Modifier.size(40.dp),
                                    shape = RoundedCornerShape(11.dp),
                                    color = Color.White
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        Icon(
                                            imageVector = Icons.Default.CheckCircle,
                                            contentDescription = null,
                                            tint = LogiOnGreen2,
                                            modifier = Modifier.size(22.dp)
                                        )
                                    }
                                }

                                Spacer(Modifier.width(11.dp))

                                Column {
                                    Text(
                                        text = "바코드 인식 완료",
                                        style = MaterialTheme.typography.titleMedium,
                                        color = LogiOnText
                                    )

                                    Text(
                                        text = detectedBarcode ?: "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = LogiOnSubText
                                    )
                                }
                            }
                        }
                    }
                }

                // 상품 조회 중
                if (isLoading) {
                    Spacer(Modifier.height(18.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(22.dp),
                            strokeWidth = 2.dp,
                            color = LogiOnGreen2
                        )

                        Spacer(Modifier.width(9.dp))

                        Text(
                            text = "상품 정보를 확인하고 있습니다.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = LogiOnSubText
                        )
                    }
                }

                // 상품 조회 오류
                errorMessage?.let { message ->
                    Spacer(Modifier.height(14.dp))

                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = CardDefaults.cardColors(
                            containerColor = LogiOnOrangeLight
                        ),
                        border = BorderStroke(1.dp, Color(0xFFF3C9A8))
                    ) {
                        Text(
                            text = message,
                            modifier = Modifier.padding(13.dp),
                            style = MaterialTheme.typography.bodyMedium,
                            color = LogiOnOrange
                        )
                    }
                }

                // 상품 조회 결과
                product?.let { result ->
                    Spacer(Modifier.height(14.dp))

                    Text(
                        text = "조회 결과",
                        style = MaterialTheme.typography.titleMedium,
                        color = LogiOnText
                    )

                    Spacer(Modifier.height(8.dp))

                    ProductResultCard(result)
                }

                // 다시 스캔
                if (detectedBarcode != null && !isLoading) {
                    Spacer(Modifier.height(12.dp))

                    OutlinedButton(
                        onClick = {
                            detectedBarcode = null
                            product = null
                            errorMessage = null
                            cameraErrorMessage = null
                            scanSession++
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(14.dp),
                        border = BorderStroke(1.dp, LogiOnGreen2),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = LogiOnGreen2
                        )
                    ) {
                        Icon(
                            imageVector = Icons.Default.QrCodeScanner,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )

                        Spacer(Modifier.width(7.dp))

                        Text(
                            text = "다시 스캔",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))
            }
        }
    }
}

// 상품 조회 결과 카드
@Composable
private fun ProductResultCard(result: BarcodeProductResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(17.dp),
        colors = CardDefaults.cardColors(containerColor = LogiOnCard),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Column(modifier = Modifier.padding(15.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    modifier = Modifier.size(40.dp),
                    shape = RoundedCornerShape(11.dp),
                    color = LogiOnGreenLight
                ) {
                    Box(contentAlignment = Alignment.Center) {
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
                        Column(modifier = Modifier.weight(1f)) {
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
                        HorizontalDivider(color = LogiOnBorder)
                        Spacer(Modifier.height(7.dp))
                    }
                }
            }
        }
    }
}

// 카메라 권한 안내
@Composable
private fun CameraPermissionCard(
    denied: Boolean,
    onRequestPermission: () -> Unit,
    onOpenSettings: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = LogiOnCard),
        border = BorderStroke(1.dp, LogiOnBorder)
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = Icons.Default.CameraAlt,
                contentDescription = null,
                tint = LogiOnGreen2,
                modifier = Modifier.size(42.dp)
            )

            Spacer(Modifier.height(10.dp))

            Text(
                text = if (denied) {
                    "카메라 권한이 거부되었습니다."
                } else {
                    "카메라 권한이 필요합니다."
                },
                style = MaterialTheme.typography.titleMedium,
                color = LogiOnText
            )

            Spacer(Modifier.height(5.dp))

            Text(
                text = "바코드를 인식하려면 카메라 사용을 허용해 주세요.",
                style = MaterialTheme.typography.bodySmall,
                color = LogiOnSubText
            )

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = onRequestPermission,
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(containerColor = LogiOnGreen2)
            ) {
                Text("카메라 권한 허용")
            }

            if (denied) {
                Spacer(Modifier.height(7.dp))

                OutlinedButton(
                    onClick = onOpenSettings,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("앱 설정에서 권한 열기")
                }
            }
        }
    }
}

// 카메라 실행 실패 안내
@Composable
private fun CameraErrorCard(
    message: String,
    onRetry: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = LogiOnOrangeLight),
        border = BorderStroke(1.dp, Color(0xFFF3C9A8))
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = Icons.Default.WarningAmber,
                contentDescription = null,
                tint = LogiOnOrange,
                modifier = Modifier.size(38.dp)
            )

            Spacer(Modifier.height(9.dp))

            Text(
                text = message,
                style = MaterialTheme.typography.titleMedium,
                color = LogiOnText
            )

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = onRetry,
                colors = ButtonDefaults.buttonColors(containerColor = LogiOnOrange)
            ) {
                Text("카메라 다시 시작")
            }
        }
    }
}

@androidx.annotation.OptIn(ExperimentalGetImage::class)
@Composable
private fun BarcodeCameraPreview(
    scanSession: Int,
    onBarcodeDetected: (String) -> Unit,
    onCameraError: (String) -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val cameraExecutor = remember(scanSession) {
        Executors.newSingleThreadExecutor()
    }

    val barcodeScanner = remember(scanSession) {
        BarcodeScanning.getClient()
    }

    val barcodeFound = remember(scanSession) {
        AtomicBoolean(false)
    }

    val previewView = remember(scanSession) {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }

    AndroidView(
        factory = { previewView },
        modifier = Modifier.fillMaxSize()
    )

    DisposableEffect(lifecycleOwner, scanSession) {
        var cameraProvider: ProcessCameraProvider? = null
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)

        cameraProviderFuture.addListener({
            try {
                cameraProvider = cameraProviderFuture.get()

                val preview = Preview.Builder().build().also {
                    it.surfaceProvider = previewView.surfaceProvider
                }

                val imageAnalysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .build()

                imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
                    if (barcodeFound.get()) {
                        imageProxy.close()
                        return@setAnalyzer
                    }

                    val mediaImage = imageProxy.image
                    if (mediaImage == null) {
                        imageProxy.close()
                        return@setAnalyzer
                    }

                    val inputImage = InputImage.fromMediaImage(
                        mediaImage,
                        imageProxy.imageInfo.rotationDegrees
                    )

                    barcodeScanner.process(inputImage)
                        .addOnSuccessListener { barcodes ->
                            val value = barcodes.firstOrNull {
                                !it.rawValue.isNullOrBlank()
                            }?.rawValue

                            if (
                                value != null &&
                                barcodeFound.compareAndSet(false, true)
                            ) {
                                ContextCompat.getMainExecutor(context).execute {
                                    onBarcodeDetected(value)
                                }
                            }
                        }
                        .addOnFailureListener {
                            Log.e("CAMERA_SCAN", "바코드 분석 실패", it)
                        }
                        .addOnCompleteListener {
                            imageProxy.close()
                        }
                }

                cameraProvider?.unbindAll()
                cameraProvider?.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    imageAnalysis
                )

                Log.d("CAMERA_SCAN", "카메라 실행 성공")
            } catch (e: Exception) {
                Log.e("CAMERA_SCAN", "카메라 실행 실패", e)

                ContextCompat.getMainExecutor(context).execute {
                    onCameraError("카메라를 시작하지 못했습니다.")
                }
            }
        }, ContextCompat.getMainExecutor(context))

        onDispose {
            cameraProvider?.unbindAll()
            barcodeScanner.close()
            cameraExecutor.shutdown()
        }
    }
}
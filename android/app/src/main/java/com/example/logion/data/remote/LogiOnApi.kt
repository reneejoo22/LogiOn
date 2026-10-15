package com.example.logion.data.remote

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path

// ==============================
// LogiOn 백엔드 API
// Android 앱에서 FastAPI 서버와 통신할 API 정의
// ==============================

// 서버 상태 확인 응답
data class HealthResponse(
    val status: String
)

// 기사 정보 응답
data class DriverResponse(
    val id: Int,
    val name: String,
    val area: String,
    @SerializedName("vehicle_number")
    val vehicleNumber: String,
    val initial: String
)

// 오늘 배송 전체 응답
data class TodayRouteResponse(
    val id: Int,
    @SerializedName("service_date")
    val serviceDate: String,
    @SerializedName("depart_at")
    val departAt: String?,
    @SerializedName("est_end_at")
    val estEndAt: String?,
    @SerializedName("synced_at")
    val syncedAt: String?,
    val summary: RouteSummaryResponse,
    @SerializedName("next_stop_id")
    val nextStopId: Int?,
    val stops: List<RouteStopResponse>
)

// 오늘 배송 진행 상황
data class RouteSummaryResponse(
    val total: Int,
    val done: Int,
    val remaining: Int,
    val progress: Float
)

// 배송지 기본 정보
data class RouteStopResponse(
    val id: Int,
    val seq: Int,
    val store: StoreResponse,
    val eta: String,
    @SerializedName("distance_km")
    val distanceKm: Double?,
    val boxes: Int,
    val notice: String?,
    val status: String,
    @SerializedName("is_next")
    val isNext: Boolean,
    @SerializedName("completed_at")
    val completedAt: String?,
    val receiver: String?
)

// 점포 정보
data class StoreResponse(
    val id: Int,
    val name: String,
    @SerializedName("short_name")
    val shortName: String,
    val address: String,
    val phone: String?,
    val lat: Double?,
    val lng: Double?
)

// 배송지 상세 정보
data class StopDetailResponse(
    val id: Int,
    val seq: Int,
    val store: StoreResponse,
    val eta: String,
    @SerializedName("distance_km")
    val distanceKm: Double?,
    val boxes: Int,
    val notice: String?,
    val status: String,
    @SerializedName("is_next")
    val isNext: Boolean,
    @SerializedName("completed_at")
    val completedAt: String?,
    val receiver: String?,
    val zones: List<ZoneResponse>,
    val items: List<StopItemResponse>,
    val issues: List<IssueResponse>
)

// 상품 구역 정보
data class ZoneResponse(
    val category: String,
    val label: String,
    val boxes: Int,
    val checked: Boolean
)

// 배송지 상품 정보
data class StopItemResponse(
    val id: Int,
    @SerializedName("product_id")
    val productId: Int,
    val name: String,
    val category: String,
    val qty: Int,
    val unit: String
)

// 등록된 이상 보고
data class IssueResponse(
    val id: Int,
    @SerializedName("product_id")
    val productId: Int?,
    @SerializedName("product_name")
    val productName: String?,
    val type: String,
    val qty: Int?,
    val unit: String?,
    val source: String,
    @SerializedName("created_at")
    val createdAt: String
)

// 상품 구역 체크 요청
data class ZoneCheckRequest(
    val checked: Boolean
)

// 배송 완료 요청
data class CompleteRequest(
    val receiver: String? = null
)

// 이상 보고 등록 요청
data class IssueCreateRequest(
    val type: String,
    @SerializedName("product_id")
    val productId: Int? = null,
    val qty: Int? = null,
    val unit: String? = null,
    val source: String = "touch"
)

// 바코드 조회 상품
data class BarcodeProductResponse(
    val id: Int,
    val name: String,
    val category: String,
    val barcode: String,
    @SerializedName("category_label")
    val categoryLabel: String,
    val deliveries: List<BarcodeDeliveryResponse>
)

// 해당 상품의 오늘 배송 정보
data class BarcodeDeliveryResponse(
    @SerializedName("stop_id")
    val stopId: Int,
    @SerializedName("store_name")
    val storeName: String,
    val status: String,
    val qty: Int,
    val unit: String
)

interface LogiOnApi {

    @GET("api/health")
    suspend fun getHealth(): HealthResponse

    @GET("api/driver")
    suspend fun getDriver(): DriverResponse

    @GET("api/routes/today")
    suspend fun getTodayRoute(): TodayRouteResponse

    @GET("api/stops/{stopId}")
    suspend fun getStopDetail(
        @Path("stopId") stopId: Int
    ): StopDetailResponse

    @PATCH("api/stops/{stopId}/zones/{category}")
    suspend fun setZoneChecked(
        @Path("stopId") stopId: Int,
        @Path("category") category: String,
        @Body body: ZoneCheckRequest
    ): StopDetailResponse

    @POST("api/stops/{stopId}/complete")
    suspend fun completeStop(
        @Path("stopId") stopId: Int,
        @Body body: CompleteRequest
    ): StopDetailResponse

    @DELETE("api/stops/{stopId}/complete")
    suspend fun cancelComplete(
        @Path("stopId") stopId: Int
    ): StopDetailResponse

    // 이상 보고 등록
    @POST("api/stops/{stopId}/issues")
    suspend fun createIssue(
        @Path("stopId") stopId: Int,
        @Body body: IssueCreateRequest
    ): IssueResponse

    // 바코드 번호로 상품 조회
    @GET("api/products/barcode/{barcode}")
    suspend fun getProductByBarcode(
        @Path("barcode") barcode: String
    ): BarcodeProductResponse
}
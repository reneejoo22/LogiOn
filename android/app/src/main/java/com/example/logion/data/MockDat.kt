package com.example.logion.data

import com.example.logion.model.DeliveryStop

val deliveryStops = listOf(

    DeliveryStop(
        id = 1,
        name = "GS25 성수연무장점",
        address = "서울 성동구 연무장길 21",
        eta = "10:25",
        status = "다음 배송",
        boxes = 12,
        distance = "1.8 km"
    ),

    DeliveryStop(
        id = 2,
        name = "CU 서울숲점",
        address = "서울 성동구 서울숲2길 32",
        eta = "10:48",
        status = "예정",
        boxes = 8,
        distance = "3.2 km"
    ),

    DeliveryStop(
        id = 3,
        name = "세븐일레븐 뚝섬점",
        address = "서울 광진구 능동로 10",
        eta = "11:16",
        status = "예정",
        boxes = 15,
        distance = "5.7 km"
    )
)
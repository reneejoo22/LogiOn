package com.example.logion.model

data class DeliveryStop(
    val id: Int,
    val name: String,
    val address: String,
    val eta: String,
    val status: String,
    val boxes: Int,
    val distance: String,
    val notice: String? = null,
    val lat: Double? = null,
    val lng: Double? = null
)
package com.example.logion.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.example.logion.R

val NotoSansKR = FontFamily(
    Font(
        R.font.notosans_kr_regular,
        FontWeight.Normal
    ),
    Font(
        R.font.notosans_kr_medium,
        FontWeight.Medium
    ),
    Font(
        R.font.notosans_kr_semibold,
        FontWeight.SemiBold
    ),
    Font(
        R.font.notosans_kr_bold,
        FontWeight.Bold
    )
)

val Typography = Typography(

    headlineLarge = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Bold,
        fontSize = 26.sp,
        lineHeight = 32.sp
    ),

    headlineMedium = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Bold,
        fontSize = 22.sp,
        lineHeight = 28.sp
    ),

    headlineSmall = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Bold,
        fontSize = 19.sp,
        lineHeight = 25.sp
    ),

    titleLarge = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Bold,
        fontSize = 17.sp,
        lineHeight = 22.sp
    ),

    titleMedium = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.SemiBold,
        fontSize = 15.sp,
        lineHeight = 20.sp
    ),

    titleSmall = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        lineHeight = 18.sp
    ),

    bodyLarge = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp
    ),

    bodyMedium = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 18.sp
    ),

    bodySmall = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Normal,
        fontSize = 11.sp,
        lineHeight = 16.sp
    ),

    labelLarge = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.SemiBold,
        fontSize = 12.sp,
        lineHeight = 17.sp
    ),

    labelMedium = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 15.sp
    ),

    labelSmall = TextStyle(
        fontFamily = NotoSansKR,
        fontWeight = FontWeight.Medium,
        fontSize = 9.sp,
        lineHeight = 13.sp
    )
)
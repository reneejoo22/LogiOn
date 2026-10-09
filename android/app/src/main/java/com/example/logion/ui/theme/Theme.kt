package com.example.logion.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LogiOnColorScheme = lightColorScheme(

    primary = LogiOnGreen2,
    secondary = LogiOnGreen,
    background = LogiOnBackground,
    surface = LogiOnCard,
    onPrimary = LogiOnCard,
    onBackground = LogiOnText,
    onSurface = LogiOnText

)

@Composable
fun LogiOnTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = LogiOnColorScheme,
        typography = Typography,
        content = content
    )
}
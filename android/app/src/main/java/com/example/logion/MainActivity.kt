package com.example.logion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.example.logion.data.ServerSettings
import com.example.logion.ui.theme.LogiOnTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ServerSettings.init(this)   // 더보기에서 저장한 보드 주소

        setContent {
            LogiOnTheme {
                LogiOnApp()
            }
        }
    }
}
package com.example.logion

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.example.logion.ui.theme.LogiOnTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            LogiOnTheme {
                LogiOnApp()
            }
        }
    }
}
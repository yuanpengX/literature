package com.literatureradar.app.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

private val Light = lightColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF3D5AFE),
    secondary = androidx.compose.ui.graphics.Color(0xFF5C6BC0),
    tertiary = androidx.compose.ui.graphics.Color(0xFF00897B),
)

private val Dark = darkColorScheme(
    primary = androidx.compose.ui.graphics.Color(0xFF8C9EFF),
    secondary = androidx.compose.ui.graphics.Color(0xFF9FA8DA),
    tertiary = androidx.compose.ui.graphics.Color(0xFF4DB6AC),
)

@Composable
fun LiteratureRadarTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val ctx = LocalContext.current
    val scheme = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            if (dark) dynamicDarkColorScheme(ctx) else dynamicLightColorScheme(ctx)
        }
        dark -> Dark
        else -> Light
    }
    MaterialTheme(
        colorScheme = scheme,
        typography = Typography,
        content = content,
    )
}

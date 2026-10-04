package com.mirror.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = MirrorCyan,
    onPrimary = TextOnAccent,
    primaryContainer = MirrorCyanGlow,
    secondary = MirrorBlue,
    background = MirrorObsidian,
    surface = MirrorSurfaceDark,
    surfaceVariant = MirrorSurfaceElevated,
    onBackground = TextPrimary,
    onSurface = TextPrimary,
    outline = MirrorBorder,
    error = MirrorCritical
)

@Composable
fun MirrorTheme(
    darkTheme: Boolean = true, // Phone-first real-world default is high-contrast dark theme
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = MirrorTypography,
        content = content
    )
}

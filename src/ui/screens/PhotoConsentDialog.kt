package com.mirror.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.mirror.ui.theme.*

/**
 * Task-level photo transmission consent dialog required before opening the camera
 * or uploading frames (SAFETY_POLICY Rule 6).
 */
@Composable
fun PhotoConsentDialog(
    onAllow: () -> Unit,
    onDecline: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDecline,
        containerColor = MirrorSurfaceElevated,
        titleContentColor = TextPrimary,
        textContentColor = TextSecondary,
        shape = RoundedCornerShape(16.dp),
        title = {
            Text(
                text = "Send photos for this task?",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = TextPrimary
            )
        },
        text = {
            Text(
                text = "MIRROR sends the photos you take to your MIRROR server, which may pass them to a " +
                    "cloud AI model so it can see what is in your space. MIRROR does not store the " +
                    "photos; the AI provider terms apply. Do not photograph people, documents or " +
                    "screens. If you say no, nothing is taken or sent.",
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
        },
        // Both buttons presented with equal visual weight (OutlinedButton) and no pre-selected default
        confirmButton = {
            OutlinedButton(
                onClick = onAllow,
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = MirrorCyan
                ),
                border = ButtonDefaults.outlinedButtonBorder.copy(
                    brush = androidx.compose.ui.graphics.SolidColor(MirrorCyan)
                )
            ) {
                Text(
                    text = "Allow for this task",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold
                )
            }
        },
        dismissButton = {
            OutlinedButton(
                onClick = onDecline,
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = TextPrimary
                ),
                border = ButtonDefaults.outlinedButtonBorder.copy(
                    brush = androidx.compose.ui.graphics.SolidColor(MirrorBorder)
                )
            ) {
                Text(
                    text = "Do not allow",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Normal
                )
            }
        }
    )
}

package com.mirror.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.mirror.ui.model.AlertSeverity
import com.mirror.ui.model.SafetyAlert
import com.mirror.ui.theme.*

/**
 * Screen 6: Safety Alert Interrupt Modal
 * High-priority safety interlock protecting the user from physical injury or environmental hazards.
 */
@Composable
fun SafetyAlertModal(
    alert: SafetyAlert,
    onAbortMission: () -> Unit,
    onDismissOrOverride: () -> Unit
) {
    val isCritical = alert.severity == AlertSeverity.CRITICAL
    val accentColor = if (isCritical) MirrorCritical else MirrorWarning
    val bgColor = if (isCritical) Color(0xFF261013) else Color(0xFF262010)

    Dialog(
        onDismissRequest = { /* Modal is persistent until explicit button action */ },
        properties = DialogProperties(dismissOnBackPress = false, dismissOnClickOutside = false)
    ) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .border(2.dp, accentColor, RoundedCornerShape(20.dp)),
            shape = RoundedCornerShape(20.dp),
            colors = CardDefaults.cardColors(containerColor = bgColor)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // Hazard Icon Shield
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(accentColor.copy(alpha = 0.2f))
                        .border(1.5.dp, accentColor, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Warning,
                        contentDescription = "Hazard Alert",
                        tint = accentColor,
                        modifier = Modifier.size(32.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Surface(
                    color = accentColor.copy(alpha = 0.2f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = if (isCritical) "CRITICAL SAFETY INTERRUPT" else "ENVIRONMENTAL SAFETY WARNING",
                        color = accentColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                    )
                }

                Spacer(modifier = Modifier.height(10.dp))

                Text(
                    text = alert.title,
                    style = MaterialTheme.typography.titleLarge,
                    color = Color.White,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(8.dp))

                Text(
                    text = alert.description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextPrimary
                )

                Spacer(modifier = Modifier.height(14.dp))

                // Recommended safe action card
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MirrorSurfaceElevated),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Text(
                            text = "Mandatory Action:",
                            fontSize = 11.sp,
                            color = accentColor,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = alert.recommendedAction,
                            fontSize = 12.sp,
                            color = TextPrimary
                        )
                    }
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Abort Button (Safe Default)
                Button(
                    onClick = onAbortMission,
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(50.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = MirrorCritical),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Halt",
                        modifier = Modifier.size(18.dp),
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "Abort Mission Immediately",
                        color = Color.White,
                        fontWeight = FontWeight.Bold
                    )
                }

                if (alert.overrideAllowed) {
                    Spacer(modifier = Modifier.height(8.dp))
                    TextButton(
                        onClick = onDismissOrOverride,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "I Have Secured The Area (Override & Continue)",
                            fontSize = 12.sp,
                            color = TextSecondary
                        )
                    }
                }
            }
        }
    }
}

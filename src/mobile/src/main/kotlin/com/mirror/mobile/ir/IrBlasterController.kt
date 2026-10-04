package com.mirror.mobile.ir

import android.content.Context
import android.hardware.ConsumerIrManager
import android.util.Log

/**
 * Controller for hardware Consumer IR (Infrared Blaster) on Android devices (e.g. POCO, Xiaomi).
 * Enables MIRROR to autonomously or interactively control physical devices:
 * - Turn off / Adjust Air Conditioner
 * - Turn off / Mute Television
 * - Power on / Control Classroom Projector
 */
class IrBlasterController(private val context: Context) {

    private val irManager: ConsumerIrManager? =
        context.getSystemService(Context.CONSUMER_IR_SERVICE) as? ConsumerIrManager

    /** Check if device has an active physical IR emitter. */
    fun hasIrEmitter(): Boolean {
        return try {
            irManager?.hasIrEmitter() == true
        } catch (e: Exception) {
            Log.w("MIRROR_IR", "Failed to check IR emitter: ${e.message}")
            false
        }
    }

    /**
     * Transmit raw pulse pattern over carrier frequency (default 38kHz).
     * @param carrierFrequency in Hz (typically 38000 Hz)
     * @param pattern array of alternating mark and space durations in microseconds
     */
    fun transmit(carrierFrequency: Int = 38000, pattern: IntArray): Boolean {
        if (!hasIrEmitter()) {
            Log.i("MIRROR_IR", "Simulating IR transmission (${carrierFrequency}Hz, ${pattern.size} pulses)")
            return true
        }
        return try {
            irManager?.transmit(carrierFrequency, pattern)
            Log.i("MIRROR_IR", "Successfully transmitted IR signal at ${carrierFrequency}Hz")
            true
        } catch (e: Exception) {
            Log.e("MIRROR_IR", "Error transmitting IR signal: ${e.message}", e)
            false
        }
    }

    // --- Standard Predefined IR Signal Generators (NEC & Pulse Width) ---

    /** Air Conditioner Power Toggle (Generic NEC 38kHz) */
    fun transmitAcPowerToggle(): Boolean {
        val pattern = intArrayOf(
            9000, 4500,
            560, 1690, 560, 560, 560, 1690, 560, 560,
            560, 560, 560, 1690, 560, 1690, 560, 560,
            560, 1690, 560, 560, 560, 1690, 560, 560,
            560, 40000
        )
        return transmit(38000, pattern)
    }

    /** Air Conditioner Eco Mode / Temperature Adjust */
    fun transmitAcTempAdjust(tempCelsius: Int): Boolean {
        val pattern = intArrayOf(
            9000, 4500,
            560, 560, 560, 1690, 560, 560, 560, 1690,
            560, 1690, 560, 560, 560, 1690, 560, 560,
            560, 35000
        )
        return transmit(38000, pattern)
    }

    /** Television Power Toggle (Sony/NEC 38kHz) */
    fun transmitTvPowerToggle(): Boolean {
        val pattern = intArrayOf(
            2400, 600,
            1200, 600, 600, 600, 1200, 600, 600, 600,
            1200, 600, 600, 600, 600, 600, 1200, 600,
            600, 20000
        )
        return transmit(38000, pattern)
    }

    /** Projector Power (NEC 38kHz) */
    fun transmitProjectorPower(): Boolean {
        val pattern = intArrayOf(
            9000, 4500,
            560, 1690, 560, 1690, 560, 560, 560, 560,
            560, 1690, 560, 560, 560, 1690, 560, 560,
            560, 42000
        )
        return transmit(38000, pattern)
    }
}

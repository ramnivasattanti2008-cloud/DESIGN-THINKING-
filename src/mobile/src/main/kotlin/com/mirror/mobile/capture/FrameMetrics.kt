package com.mirror.mobile.capture

/**
 * On-device frame quality. The backend refuses to judge blurry or dark frames, so these numbers
 * decide whether a verification can happen at all. Thresholds are heuristics, UNVERIFIED on
 * real photos.
 */
object FrameMetrics {
    /** Laplacian variance at or above this counts as fully sharp. Heuristic. */
    const val SHARP_VARIANCE = 300.0

    /** Mean luma 0..1. Empty input counts as dark. */
    fun brightness(luma: IntArray): Float =
        if (luma.isEmpty()) 0f else (luma.average() / 255.0).toFloat().coerceIn(0f, 1f)

    /** 0 = sharp, 1 = unusable. Variance of a 4-neighbour Laplacian over the luma plane. */
    fun blur(luma: IntArray, width: Int, height: Int): Float {
        if (width < 3 || height < 3 || luma.size < width * height) return 1f
        var sum = 0.0
        var sumSq = 0.0
        var n = 0
        for (y in 1 until height - 1) {
            for (x in 1 until width - 1) {
                val i = y * width + x
                val lap = (4 * luma[i] - luma[i - 1] - luma[i + 1] - luma[i - width] - luma[i + width]).toDouble()
                sum += lap
                sumSq += lap * lap
                n++
            }
        }
        val mean = sum / n
        val variance = sumSq / n - mean * mean
        return (1.0 - variance / SHARP_VARIANCE).coerceIn(0.0, 1.0).toFloat()
    }
}

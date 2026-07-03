package com.horseracing.audiofirst

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.MotionEvent
import android.view.View
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min

data class MobileRaceCommand(
    val throttleDelta: Float = 0f,
    val lateralDelta: Float = 0f,
    val pushRequested: Boolean = false,
    val jumpRequested: Boolean = false,
    val duckRequested: Boolean = false,
    val requestStatus: Boolean = false,
)

class RaceSurfaceView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : View(context, attrs) {
    private val backgroundPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(16, 27, 23) }
    private val lanePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(32, 88, 62) }
    private val focusPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.rgb(245, 220, 130) }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textSize = 42f
    }

    private var downX = 0f
    private var downY = 0f
    private var downAtMs = 0L
    private var lastTapAtMs = 0L
    private var lastCommand = MobileRaceCommand(requestStatus = true)
    private var lastAnnouncement = context.getString(R.string.race_surface_ready)
    private var audioController: AndroidAudioController? = null

    init {
        isFocusable = true
        isClickable = true
        contentDescription = context.getString(R.string.race_surface_description)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), backgroundPaint)
        val laneWidth = width / 3f
        for (index in 0 until 3) {
            val left = index * laneWidth + 10f
            canvas.drawRoundRect(RectF(left, 40f, left + laneWidth - 20f, height - 40f), 24f, 24f, lanePaint)
        }
        canvas.drawCircle(width / 2f, height * 0.72f, 44f, focusPaint)
        canvas.drawText(lastAnnouncement, 32f, 72f, textPaint)
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                downX = event.x
                downY = event.y
                downAtMs = event.eventTime
                performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                return true
            }
            MotionEvent.ACTION_UP -> {
                val command = commandFromTouch(event)
                publishCommand(command)
                if (isTap(event)) {
                    performClick()
                }
                return true
            }
        }
        return true
    }

    override fun performClick(): Boolean {
        super.performClick()
        announceForAccessibility(context.getString(R.string.race_surface_tap_confirmed))
        return true
    }

    fun currentCommand(): MobileRaceCommand = lastCommand

    fun setAudioController(controller: AndroidAudioController?) {
        audioController = controller
    }

    private fun commandFromTouch(event: MotionEvent): MobileRaceCommand {
        val dx = event.x - downX
        val dy = event.y - downY
        val durationMs = max(0L, event.eventTime - downAtMs)
        if (event.pointerCount >= 2) {
            return MobileRaceCommand(requestStatus = true)
        }
        if (durationMs >= LONG_PRESS_MS && isTap(event)) {
            return MobileRaceCommand(requestStatus = true)
        }
        if (isDoubleTap(event)) {
            lastTapAtMs = event.eventTime
            return MobileRaceCommand(pushRequested = true)
        }
        if (isTap(event)) {
            lastTapAtMs = event.eventTime
            return MobileRaceCommand()
        }
        if (max(abs(dx), abs(dy)) >= MIN_SWIPE_PX && abs(dy) >= abs(dx)) {
            return MobileRaceCommand(jumpRequested = dy < 0f, duckRequested = dy > 0f)
        }
        return MobileRaceCommand(
            throttleDelta = axis(-dy),
            lateralDelta = axis(dx),
        )
    }

    private fun publishCommand(command: MobileRaceCommand) {
        lastCommand = command
        lastAnnouncement = labelFor(command)
        announceForAccessibility(lastAnnouncement)
        audioController?.handleCommand(command, lastAnnouncement)
        performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY)
        invalidate()
    }

    private fun labelFor(command: MobileRaceCommand): String {
        return when {
            command.jumpRequested -> context.getString(R.string.race_action_jump)
            command.duckRequested -> context.getString(R.string.race_action_duck)
            command.pushRequested -> context.getString(R.string.race_action_push)
            command.requestStatus -> context.getString(R.string.race_action_status)
            command.lateralDelta > 0f -> context.getString(R.string.race_action_right)
            command.lateralDelta < 0f -> context.getString(R.string.race_action_left)
            command.throttleDelta > 0f -> context.getString(R.string.race_action_accelerate)
            command.throttleDelta < 0f -> context.getString(R.string.race_action_slow)
            else -> context.getString(R.string.race_action_hold)
        }
    }

    private fun axis(distancePx: Float): Float {
        val value = max(-1f, min(1f, distancePx / AXIS_FULL_SCALE_PX))
        return if (abs(value) < AXIS_DEADZONE) 0f else value
    }

    private fun isTap(event: MotionEvent): Boolean {
        return max(abs(event.x - downX), abs(event.y - downY)) < TAP_SLOP_PX
    }

    private fun isDoubleTap(event: MotionEvent): Boolean {
        return isTap(event) && event.eventTime - lastTapAtMs <= DOUBLE_TAP_MS
    }

    companion object {
        private const val AXIS_FULL_SCALE_PX = 160f
        private const val AXIS_DEADZONE = 0.12f
        private const val MIN_SWIPE_PX = 48f
        private const val TAP_SLOP_PX = 24f
        private const val DOUBLE_TAP_MS = 350L
        private const val LONG_PRESS_MS = 450L
    }
}

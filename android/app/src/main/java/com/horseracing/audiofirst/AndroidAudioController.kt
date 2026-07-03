package com.horseracing.audiofirst

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.SoundPool
import android.speech.tts.TextToSpeech

class AndroidAudioController(context: Context) {
    private val appContext = context.applicationContext
    private val audioManager = appContext.getSystemService(AudioManager::class.java)
    private val gameAudioAttributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_GAME)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
        .build()
    private val speechAudioAttributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
        .build()
    private val focusListener = AudioManager.OnAudioFocusChangeListener { change ->
        hasAudioFocus = change == AudioManager.AUDIOFOCUS_GAIN
        ducked = change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK
    }
    private val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
        .setAudioAttributes(gameAudioAttributes)
        .setAcceptsDelayedFocusGain(true)
        .setOnAudioFocusChangeListener(focusListener)
        .build()
    private val soundPool = SoundPool.Builder()
        .setMaxStreams(MAX_STREAMS)
        .setAudioAttributes(gameAudioAttributes)
        .build()
    private val cueIds = mutableMapOf<String, Int>()
    private var textToSpeech: TextToSpeech? = null
    private var ttsReady = false
    private var hasAudioFocus = false
    private var ducked = false

    fun start() {
        hasAudioFocus = audioManager.requestAudioFocus(focusRequest) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        if (textToSpeech == null) {
            textToSpeech = TextToSpeech(appContext) { status ->
                ttsReady = status == TextToSpeech.SUCCESS
                if (ttsReady) {
                    textToSpeech?.setAudioAttributes(speechAudioAttributes)
                }
            }
        }
    }

    fun stop() {
        audioManager.abandonAudioFocusRequest(focusRequest)
        hasAudioFocus = false
        textToSpeech?.stop()
    }

    fun shutdown() {
        stop()
        textToSpeech?.shutdown()
        textToSpeech = null
        ttsReady = false
        soundPool.release()
        cueIds.clear()
    }

    fun registerCue(cueId: String, rawResourceId: Int) {
        if (cueId.isBlank()) {
            throw IllegalArgumentException("cueId must be non-empty")
        }
        cueIds[cueId] = soundPool.load(appContext, rawResourceId, 1)
    }

    fun handleCommand(command: MobileRaceCommand, spokenLabel: String) {
        if (command.requestStatus) {
            speak(spokenLabel)
            playCue("status")
            return
        }
        when {
            command.jumpRequested -> playCue("jump")
            command.duckRequested -> playCue("duck")
            command.pushRequested -> playCue("push")
            command.lateralDelta != 0f -> playCue("steer")
            command.throttleDelta != 0f -> playCue("pace")
        }
        if (command.jumpRequested || command.duckRequested || command.pushRequested) {
            speak(spokenLabel)
        }
    }

    fun speak(text: String) {
        if (!ttsReady || text.isBlank()) {
            return
        }
        textToSpeech?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "race-status")
    }

    fun playCue(cueId: String) {
        val soundId = cueIds[cueId] ?: return
        val volume = if (ducked) DUCKED_VOLUME else FULL_VOLUME
        if (hasAudioFocus) {
            soundPool.play(soundId, volume, volume, 1, 0, 1f)
        }
    }

    companion object {
        private const val MAX_STREAMS = 8
        private const val FULL_VOLUME = 1.0f
        private const val DUCKED_VOLUME = 0.35f
    }
}

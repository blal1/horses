package com.horseracing.audiofirst

import android.app.Activity
import android.os.Bundle

class MainActivity : Activity() {
    private lateinit var audioController: AndroidAudioController
    private lateinit var raceSurfaceView: RaceSurfaceView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        audioController = AndroidAudioController(this)
        raceSurfaceView = RaceSurfaceView(this).apply {
            setAudioController(audioController)
        }
        setContentView(raceSurfaceView)
    }

    override fun onResume() {
        super.onResume()
        audioController.start()
    }

    override fun onPause() {
        audioController.stop()
        super.onPause()
    }

    override fun onDestroy() {
        audioController.shutdown()
        super.onDestroy()
    }
}

package org.duchinese.reader

/** Gesture-only diagnostics; disabled unless explicitly enabled by the host. */
object ReaderDiagnostics {
    var enabled = false
    internal fun log(message: String) {
        if (enabled) println("ReaderGesture $message")
    }
}

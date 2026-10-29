package org.duchinese.reader
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) { super.onCreate(savedInstanceState); ReaderDiagnostics.enabled = BuildConfig.DEBUG; setContent { ReaderApp() } }
}

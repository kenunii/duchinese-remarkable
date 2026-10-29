package org.duchinese.reader

import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.*
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.russhwolf.settings.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import org.jetbrains.compose.resources.ExperimentalResourceApi
import org.jetbrains.compose.resources.decodeToImageBitmap
import reader.resources.Res
import kotlin.math.*

private val json=Json { ignoreUnknownKeys=true }
@OptIn(ExperimentalResourceApi::class)
@Composable fun ReaderApp() {
    var book by remember { mutableStateOf<Book?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        try { book=withContext(Dispatchers.Default) { json.decodeFromString<Book>(Res.readBytes("files/textbook/book.json").decodeToString()) } }
        catch(e: Exception) { error="Unable to open the bundled textbook." }
    }
    MaterialTheme(colorScheme=lightColorScheme()) {
        Surface(Modifier.fillMaxSize()) {
            val loaded=book
            if(loaded!=null) Reader(loaded)
            else Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center) { if(error!=null) Text(error!!) else CircularProgressIndicator() }
        }
    }
}

@Composable private fun Reader(book: Book) {
    val settings=remember { Settings() }
    val key="pdf-${book.id}-page"
    val initial=remember { book.pages.indexOfFirst { it.source_page==settings.getInt(key,book.pages.first().source_page) }.coerceAtLeast(0) }
    val scope=rememberCoroutineScope()
    val pager=rememberPagerState(initialPage=initial, pageCount={book.pages.size})
    var selected by remember { mutableStateOf<Word?>(null) }
    var translation by remember { mutableStateOf(false) }
    var zoomed by remember { mutableStateOf(false) }
    var indicator by remember { mutableStateOf(true) }
    val page=book.pages[pager.settledPage]
    LaunchedEffect(pager.settledPage,pager.isScrollInProgress) {
        ReaderDiagnostics.log("pager settled=${pager.settledPage+1} current=${pager.currentPage+1} moving=${pager.isScrollInProgress} zoomLocked=$zoomed")
        if(pager.isScrollInProgress) { selected=null; indicator=true }
        else {
            settings.putInt(key,page.source_page)
            indicator=true
            delay(1600)
            indicator=false
        }
    }
    Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        TextButton(onClick={translation=!translation},modifier=Modifier.fillMaxWidth()) {
            Text(if(translation) selected?.let { page.sentences[it.sentence].translation } ?: "Tap a word for its sentence translation" else "Show sentence translation")
        }
        Box(Modifier.weight(1f).fillMaxWidth().background(Color(0xffeeeeee))) {
            HorizontalPager(state=pager, beyondViewportPageCount=1, userScrollEnabled=!zoomed,
                key={book.pages[it].source_page}, modifier=Modifier.fillMaxSize().testTag("pagePager")) { index ->
                ReaderPage(book.pages[index],active=index==pager.settledPage,
                    turning=pager.isScrollInProgress,
                    selected=if(index==pager.settledPage) selected else null,
                    onPinchStart={
                        zoomed=true
                        selected=null
                        scope.launch { pager.scrollToPage(pager.settledPage) }
                    }, onSelected={selected=it}, onZoomed={if(index==pager.settledPage) zoomed=it})
            }
            if(indicator) Surface(Modifier.align(Alignment.BottomCenter).padding(16.dp).testTag("pageIndicator"),
                shape=MaterialTheme.shapes.extraLarge,color=Color.Black.copy(alpha=.65f),contentColor=Color.White) {
                Text("${book.pages[pager.currentPage].source_page} / ${book.pages.size}",Modifier.padding(horizontal=14.dp,vertical=6.dp))
            }
        }
    }
}

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

@OptIn(ExperimentalResourceApi::class)
@Composable internal fun ReaderPage(page: Page, active: Boolean, turning: Boolean, selected: Word?,
    onPinchStart: () -> Unit, onSelected: (Word?) -> Unit, onZoomed: (Boolean) -> Unit) {
    // Pointer coroutines outlive recompositions, especially on prefetched pages.
    // Read current parameters without restarting/cancelling an in-flight gesture.
    val currentActive by rememberUpdatedState(active)
    val currentTurning by rememberUpdatedState(turning)
    val selectWord by rememberUpdatedState(onSelected)
    val setZoomed by rememberUpdatedState(onZoomed)
    val startPinch by rememberUpdatedState(onPinchStart)
    var bitmap by remember(page.source_page) { mutableStateOf<ImageBitmap?>(null) }
    var imageError by remember(page.source_page) { mutableStateOf(false) }
    var zoom by remember { mutableStateOf(1f) }
    var pan by remember { mutableStateOf(Point(0f,0f)) }
    var size by remember { mutableStateOf(IntSize.Zero) }
    var popupHeight by remember { mutableStateOf(0) }
    val density=LocalDensity.current.density
    LaunchedEffect(page.source_page) {
        try { bitmap=withContext(Dispatchers.Default) { Res.readBytes("files/textbook/${page.image_file}").decodeToImageBitmap() } }
        catch(e: kotlinx.coroutines.CancellationException) { throw e }
        catch(e: Exception) { imageError=true }
    }
    LaunchedEffect(active) { if(!active) {zoom=1f;pan=Point(0f,0f)} else onZoomed(zoom>1.01f) }
    Box(Modifier.fillMaxSize()) {
        val image=bitmap
        if(image!=null) Canvas(Modifier.fillMaxSize().clipToBounds().testTag(if(active) "pageCanvas" else "page-${page.source_page}")
            .semantics { stateDescription="Page ${page.source_page}; Zoom $zoom; Turning $turning" }
            .onSizeChanged {size=it;pan=clampPan(page,it.width.toFloat(),it.height.toFloat(),zoom,pan)}
            .pointerInput(page.source_page,size) {
                detectTapGestures(onPress={ point ->
                    if(tryAwaitRelease() && currentActive && !currentTurning) {
                        val t=transform(page,size.width.toFloat(),size.height.toFloat(),zoom,pan)
                        selectWord(hitWord(page,t.source(point.x,point.y),10*density/t.scale))
                    }
                })
            }
            .pointerInput(page.source_page,size) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed=false)
                    var transforming=false
                    ReaderDiagnostics.log("down page=${page.source_page} active=$currentActive moving=$currentTurning zoom=$zoom")
                    try {
                    do {
                        // Claim pinch/zoomed pan before the pager sees motion. A one-finger
                        // drag at fit is left entirely to HorizontalPager's drag/fling logic.
                        val event=awaitPointerEvent(PointerEventPass.Initial)
                        val pressed=event.changes.count {it.pressed}
                        if(pressed>1 && !transforming && currentActive) {
                            transforming=true
                            ReaderDiagnostics.log("pinchStart page=${page.source_page} moving=$currentTurning zoom=$zoom")
                            startPinch()
                        }
                        if(currentActive && (transforming || (!currentTurning && zoom>1.01f))) {
                            val factor=event.calculateZoom()
                            val delta=event.calculatePan()
                            val center=event.calculateCentroid(useCurrent=false)
                            if(factor!=1f || delta!=Offset.Zero) {
                                val old=zoom;zoom=(zoom*factor).coerceIn(1f,6f)
                                val ratio=zoom/old
                                val cx=if(center.x.isFinite()) center.x-size.width/2f else 0f
                                val cy=if(center.y.isFinite()) center.y-size.height/2f else 0f
                                pan=clampPan(page,size.width.toFloat(),size.height.toFloat(),zoom,
                                    Point(pan.x*ratio+cx*(1-ratio)+delta.x,pan.y*ratio+cy*(1-ratio)+delta.y))
                                setZoomed(transforming || zoom>1.01f);selectWord(null)
                                event.changes.forEach {it.consume()}
                            } else if(transforming) event.changes.forEach {it.consume()}
                        }
                    } while(event.changes.any {it.pressed})
                    } finally {
                        if(transforming) setZoomed(zoom>1.01f)
                        ReaderDiagnostics.log("end page=${page.source_page} pinch=$transforming active=$currentActive moving=$currentTurning zoom=$zoom")
                    }
                }
            }) {
            val t=transform(page,size.width.toFloat(),size.height.toFloat(),zoom,pan)
            withTransform({translate(t.x,t.y);scale(t.scale,t.scale,pivot=Offset.Zero)}) {
                drawImage(image)
                selected?.boxes?.forEach {b -> drawRect(Color(0x553b82f6),Offset(b[0],b[1]),androidx.compose.ui.geometry.Size(b[2],b[3]))}
            }
        } else if(imageError) Text("Unable to load this page",Modifier.align(Alignment.Center))
        else CircularProgressIndicator(Modifier.align(Alignment.Center))
            selected?.let { word ->
                val t=transform(page,size.width.toFloat(),size.height.toFloat(),zoom,pan)
                val box=word.boxes.first()
                val above=box[1]*t.scale+t.y-popupHeight-8*density
                val below=(box[1]+box[3])*t.scale+t.y+8*density
                val popupY=(if(above>=0) above else below).coerceIn(0f,max(0f,size.height-popupHeight.toFloat()))
                Card(onClick={onSelected(null)}, modifier=Modifier.testTag("wordPopup").align(Alignment.TopCenter).offset { IntOffset(0,popupY.toInt()) }
                    .padding(horizontal=12.dp).widthIn(max=420.dp).fillMaxWidth().onSizeChanged { popupHeight=it.height }) {
                    Column(Modifier.padding(16.dp)) {
                        Text(word.hanzi,style=MaterialTheme.typography.headlineSmall)
                        Text(word.pinyin,style=MaterialTheme.typography.titleMedium)
                        Text(word.meaning)
                    }
                }
            }
    }
}

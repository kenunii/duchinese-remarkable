package org.duchinese.reader
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.SemanticsProperties
import org.junit.Rule
import org.junit.Test
import org.junit.Assert.assertTrue
import com.russhwolf.settings.Settings
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import org.jetbrains.compose.resources.ExperimentalResourceApi
import reader.resources.Res

@OptIn(ExperimentalResourceApi::class)
class ReaderGestureTest {
    private fun SemanticsNodeInteraction.pinchIn() = performTouchInput {
        pinch(Offset(center.x-40,center.y),Offset(center.x-120,center.y),Offset(center.x+40,center.y),Offset(center.x+120,center.y))
    }
    private fun SemanticsNodeInteraction.fit() = performTouchInput {
        pinch(Offset(center.x-150,center.y),Offset(center.x-15,center.y),Offset(center.x+150,center.y),Offset(center.x+15,center.y))
    }
    @get:Rule val rule=createAndroidComposeRule<MainActivity>()
    @Test fun prefetchedPagesRemainZoomable() {
        fun canvas()=rule.onNodeWithTag("pageCanvas")
        fun ready() { rule.waitUntil(15000) { rule.onAllNodesWithTag("pageCanvas").fetchSemanticsNodes().any {it.config[SemanticsProperties.StateDescription].endsWith("Turning false")} } }
        ready()
        repeat(8) {
            // Let the adjacent page's handler start while that page is inactive.
            Thread.sleep(600)
            canvas().performTouchInput { swipeLeft() }
            ready()
            canvas().pinchIn()
            assertTrue("Prefetched page must accept zoom on visit $it",!canvas().fetchSemanticsNode().config[SemanticsProperties.StateDescription].contains("Zoom 1.0;"))
            canvas().fit()
        }
        repeat(12) { rule.onNodeWithTag("pagePager").performTouchInput { swipeRight(durationMillis=90) } }
        ready()
        repeat(3) {
            canvas().performTouchInput { pinch(Offset(center.x-40,center.y),Offset(center.x-140,center.y),Offset(center.x+40,center.y),Offset(center.x+140,center.y)) }
            assertTrue("Pinch after rapid page turns must zoom",!canvas().fetchSemanticsNode().config[SemanticsProperties.StateDescription].contains("Zoom 1.0;"))
            canvas().fit()
        }
    }
    @Test fun swipeZoomLookupAndPersistence() {
        val book=runBlocking { Json { ignoreUnknownKeys=true }.decodeFromString<Book>(Res.readBytes("files/textbook/book.json").decodeToString()) }
        fun ready() { rule.waitUntil(15000) { rule.onAllNodesWithTag("pageCanvas").fetchSemanticsNodes().any { it.config[SemanticsProperties.StateDescription].endsWith("Turning false") } } }
        ready()
        val saved=Settings().getInt("pdf-${book.id}-page",1)
        // Start from whatever page was persisted by an earlier run.
        repeat(saved-1) { rule.onNodeWithTag("pageCanvas").performTouchInput { swipeRight() };ready() }
        rule.onNodeWithText("Chinese PDF Reader").assertDoesNotExist()
        rule.onNodeWithText("Fit").assertDoesNotExist()
        repeat(23) { rule.onNodeWithTag("pageCanvas").performTouchInput { swipeLeft() };ready() }
        rule.onNodeWithText("24 / 50").assertExists()
        rule.onNodeWithTag("pageIndicator").assertExists()
        val canvas=rule.onNodeWithTag("pageCanvas")
        // Keep the finger down: the page must already move, not wait for release.
        val before=canvas.getUnclippedBoundsInRoot().left.value
        canvas.performTouchInput {
            down(center)
            moveTo(Offset(center.x-width*.15f,center.y),600)
        }
        val dragged=canvas.getUnclippedBoundsInRoot().left.value
        assertTrue("Page should track the held finger",dragged<before-10f)
        assertTrue("Unsettled drag must not save a new page",Settings().getInt("pdf-${book.id}-page",0)==24)
        canvas.performTouchInput { advanceEventTime(400); up() }
        ready()
        canvas.assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription,"Page 24; Zoom 1.0; Turning false"))
        assertTrue("Short slow drag snaps back",kotlin.math.abs(canvas.getUnclippedBoundsInRoot().left.value-before)<1f)
        canvas.performTouchInput { swipeUp() }
        rule.onNodeWithText("24 / 50").assertExists()
        canvas.performTouchInput { doubleClick(center) }
        canvas.assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription,"Page 24; Zoom 1.0; Turning false"))
        canvas.performTouchInput { pinch(Offset(center.x-40,center.y),Offset(center.x-120,center.y),Offset(center.x+40,center.y),Offset(center.x+120,center.y)) }
        assertTrue(canvas.fetchSemanticsNode().config[SemanticsProperties.StateDescription]!="Page 24; Zoom 1.0; Turning false")
        canvas.fit()
        // Start a page drag before the second finger lands: pinch must take over.
        canvas.performTouchInput {
            down(0,Offset(center.x-60,center.y))
            moveTo(0,Offset(center.x-140,center.y),200)
        }
        canvas.performTouchInput {
            down(1,Offset(center.x+60,center.y))
            moveTo(0,Offset(center.x-240,center.y),200)
            moveTo(1,Offset(center.x+180,center.y),200)
            up(1);up(0)
        }
        ready()
        assertTrue("Pinch must take over from an already-started page drag",canvas.fetchSemanticsNode().config[SemanticsProperties.StateDescription]!="Page 24; Zoom 1.0; Turning false")
        assertTrue(Settings().getInt("pdf-${book.id}-page",0)==24)
        canvas.fit()
        val page=book.pages[23];val word=page.words.first { it.pinyin.isNotBlank() };val b=word.boxes.first()
        val bounds=canvas.fetchSemanticsNode().boundsInRoot
        val t=transform(page,bounds.width,bounds.height,1f,Point(0f,0f))
        canvas.performTouchInput { click(Offset((b[0]+b[2]/2)*t.scale+t.x,(b[1]+b[3]/2)*t.scale+t.y)) }
        rule.waitUntil(2000) { rule.onAllNodesWithText(word.pinyin).fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithText(word.pinyin).assertExists()
        rule.onNodeWithText(word.meaning).assertExists()
        rule.onNodeWithText("Show sentence translation").performClick()
        rule.onNodeWithText(page.sentences[word.sentence].translation).assertExists()
        rule.onNodeWithText("Close").assertDoesNotExist()
        rule.onNodeWithTag("wordPopup").performClick()
        rule.onNodeWithTag("wordPopup").assertDoesNotExist()
        rule.waitUntil(4000) { rule.onAllNodesWithTag("pageIndicator").fetchSemanticsNodes().isEmpty() }
        assertTrue(Settings().getInt("pdf-${book.id}-page",0)==24)
    }
}

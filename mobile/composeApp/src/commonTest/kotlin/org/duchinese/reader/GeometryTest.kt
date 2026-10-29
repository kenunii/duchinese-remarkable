package org.duchinese.reader
import kotlin.test.*
class GeometryTest {
    private val word=Word("你好","nǐ hǎo","hello",0,listOf(listOf(230f,340f,60f,25f)))
    private val page=Page(1,"page.png",2000,1500,listOf(200f,300f,1000f,1100f),listOf(word),listOf(Sentence("你好","Hello")))
    @Test fun tapFollowsCropZoomAndPan() {
        for (zoom in listOf(1f,2f,6f)) for (width in listOf(390f,844f)) {
            val t=transform(page,width,700f,zoom,Point(-70f,20f))
            val source=t.source(250*t.scale+t.x,350*t.scale+t.y)
            assertEquals(250f,source.x,.001f);assertEquals(350f,source.y,.001f)
            assertEquals(word,hitWord(page,source,5f))
            assertNull(hitWord(page,Point(900f,900f),5f))
        }
    }
    @Test fun swipeBoundsAndVerticalRejection() {
        assertEquals(1,swipePage(0,50,-150f,10f,60f))
        assertEquals(0,swipePage(0,50,150f,0f,60f))
        assertEquals(49,swipePage(49,50,-150f,0f,60f))
        assertEquals(20,swipePage(20,50,20f,180f,60f))
        assertEquals(20,swipePage(20,50,30f,0f,60f))
    }
    @Test fun fitCannotPanAndZoomCannotLosePage() {
        assertEquals(Point(0f,0f),clampPan(page,400f,800f,1f,Point(999f,-999f)))
        assertEquals(Point(200f,-40f),clampPan(page,400f,800f,2f,Point(999f,-999f)))
    }
}

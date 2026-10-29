package org.duchinese.reader
import kotlinx.serialization.Serializable
import kotlin.math.*
@Serializable data class Book(val id: String, val title: String, val pages: List<Page>)
@Serializable data class Page(val source_page: Int, val image_file: String, val image_width: Int, val image_height: Int, val view: List<Float>, val words: List<Word>, val sentences: List<Sentence>)
@Serializable data class Word(val hanzi: String, val pinyin: String, val meaning: String, val sentence: Int, val boxes: List<List<Float>>)
@Serializable data class Sentence(val text: String, val translation: String)
data class Point(val x: Float, val y: Float)
data class Transform(val scale: Float, val x: Float, val y: Float) {
    fun source(x: Float, y: Float) = Point((x-this.x)/scale, (y-this.y)/scale)
}
fun transform(page: Page, width: Float, height: Float, zoom: Float, pan: Point): Transform {
    val v=page.view
    val s=min(width/v[2],height/v[3])*zoom
    return Transform(s,(width-v[2]*s)/2+pan.x-v[0]*s,(height-v[3]*s)/2+pan.y-v[1]*s)
}
fun clampPan(page: Page, width: Float, height: Float, zoom: Float, pan: Point): Point {
    val s=min(width/page.view[2],height/page.view[3])*zoom
    val x=max(0f,(page.view[2]*s-width)/2); val y=max(0f,(page.view[3]*s-height)/2)
    return Point(if(x==0f) 0f else pan.x.coerceIn(-x,x),if(y==0f) 0f else pan.y.coerceIn(-y,y))
}
fun hitWord(page: Page, point: Point, tolerance: Float): Word? = page.words.filter { it.pinyin.isNotBlank() }
    .map { word -> word to word.boxes.minOf { b ->
        val dx=maxOf(b[0]-point.x,0f,point.x-b[0]-b[2]); val dy=maxOf(b[1]-point.y,0f,point.y-b[1]-b[3]); sqrt(dx*dx+dy*dy)
    } }.filter { it.second<=tolerance }.minByOrNull { it.second }?.first
fun swipePage(current: Int, count: Int, dx: Float, dy: Float, threshold: Float): Int =
    if(abs(dx)>=threshold && abs(dx)>abs(dy)*1.5f) (current+if(dx<0) 1 else -1).coerceIn(0,count-1) else current

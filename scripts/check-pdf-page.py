#!/usr/bin/env python3
"""Exercise the actual QML component and tap transforms offscreen.
Usage: QT_QPA_PLATFORM=offscreen python3 scripts/check-pdf-page.py BUILD_DIR
"""
import json
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtCore import QResource, QUrl, QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlExpression, QQmlEngine
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

build = Path(sys.argv[1]).resolve()
app = QGuiApplication([])
assert QResource.registerResource(str(build/'resources.rcc'), '/isolated-app')
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.resize(1404,1872)
view.setSource(QUrl('qrc:/isolated-app/pdf-test/PdfPage.qml'))
assert view.status() == QQuickView.Ready, [e.toString() for e in view.errors()]
view.show()
QTest.qWait(500)
root=view.rootObject()
ctx=QQmlEngine.contextForObject(root)
def js(s):
    expression=QQmlExpression(ctx,root,s)
    result=expression.evaluate()
    assert not expression.hasError(),expression.error().toString()
    return result[0] if isinstance(result,tuple) else result

def click_word(index, box_index=0):
    point=js(f'pageImage.mapToItem(root, (book.words[{index}].boxes[{box_index}][0]+book.words[{index}].boxes[{box_index}][2]/2)*imageScale, (book.words[{index}].boxes[{box_index}][1]+book.words[{index}].boxes[{box_index}][3]/2)*imageScale)')
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())))
    QTest.qWait(40)
    assert root.property('selectedWord')==index,(index,root.property('selectedWord'))
    assert js('popup.x >= popup.availableRect.x && popup.x + popup.width <= popup.availableRect.x + popup.availableRect.width + 0.1')
    assert js('popup.y >= popup.availableRect.y && popup.y + popup.height <= popup.availableRect.y + popup.availableRect.height + 0.1')
    root.setProperty('selectedWord',-1)

# Every annotated region, including every part of a word spanning lines.
count=int(js('book.words.length')); hits=0
for i in range(count):
    if not js(f'book.words[{i}].pinyin'): continue
    for j in range(int(js(f'book.words[{i}].boxes.length'))):
        click_word(i,j);hits+=1
# Full page letterboxing and zoom/pan use the same source coordinates.
root.setProperty('fullPage',True); QTest.qWait(40);click_word(1)
root.setProperty('fullPage',False);root.setProperty('zoom',1.6);QTest.qWait(40)
click_word(1)
js('viewport.contentY = 550');QTest.qWait(40)
panned=next(i for i in range(count) if js(f'book.words[{i}].hanzi')=='幼儿园')
click_word(panned)
# Hit-test invariance at all source boxes even when outside viewport.
for i in range(count):
    if js(f'book.words[{i}].pinyin'):
        assert js(f'hitTest(book.words[{i}].boxes[0][0]+book.words[{i}].boxes[0][2]/2,book.words[{i}].boxes[0][1]+book.words[{i}].boxes[0][3]/2)')==i
root.setProperty('zoom',1);js('resetView()');QTest.qWait(40)
assert js('hitTest(3000,1000)')==-1
view.grabWindow().save(str(build/'preview-page.png'))
idiom=next(i for i in range(count) if js(f'book.words[{i}].hanzi')=='轻而易举')
click_word(idiom)
root.setProperty('selectedWord',idiom)
# The shared top bar toggles translation; choosing another word preserves the setting.
QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(700,78))
QTest.qWait(40)
assert root.property('showTranslation')
assert js('translationArea.translation') == js(f'book.sentences[book.words[{idiom}].sentence].translation')
root.setProperty('selectedWord',-1)
click_word(1)
assert root.property('showTranslation')
click_word(idiom)
root.setProperty('selectedWord',idiom)
# The word popup stays adjacent to the tapped word, never a fixed top/bottom panel.
assert js('Math.abs(popup.y - (popup.wordRect.y + popup.wordRect.height + 10)) < 1 || Math.abs(popup.y + popup.height + 10 - popup.wordRect.y) < 1')
QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(int(js('popup.x + 30')),int(js('popup.y + 30'))))
QTest.qWait(40)
assert root.property('selectedWord') == -1
click_word(idiom)
root.setProperty('selectedWord',idiom)
QTest.qWait(100)
view.grabWindow().save(str(build/'preview-lookup.png'))
print(f'PASS: {hits} real word taps; full-page, zoom and pan transforms; shared translation toggle, persistent reveal, popup placement/dismissal; rendered page and lookup')

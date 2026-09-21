#!/usr/bin/env python3
"""Exercise actual QML page swipes, lookup transforms and disk-persisted position."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
verify_saved='--verify-saved' in sys.argv
if not verify_saved:
    isolated=tempfile.TemporaryDirectory(prefix='pdf-reader-state-')
    os.environ['XDG_DATA_HOME']=isolated.name
from PySide6.QtCore import QResource,QUrl,QPoint,Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine,QQmlExpression
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest
root_path=Path(sys.argv[1]).resolve();app=QGuiApplication([])
app.setOrganizationName('PdfReaderCheck');app.setApplicationName('PdfReaderCheck')
assert QResource.registerResource(str(root_path/'resources.rcc'),'/check')
view=QQuickView();view.setResizeMode(QQuickView.SizeRootObjectToView);view.resize(1404,1872)
view.setSource(QUrl('qrc:/check/pdf-test/PdfPage.qml'))
assert view.status()==QQuickView.Ready,[e.toString() for e in view.errors()]
view.show();root=view.rootObject();ctx=QQmlEngine.contextForObject(root)
def js(code):
    e=QQmlExpression(ctx,root,code);r=e.evaluate();assert not e.hasError(),e.error().toString()
    return r[0] if isinstance(r,tuple) else r

def ready():
    for _ in range(150):
        QTest.qWait(20)
        if js('pageImage.status===Image.Ready'):return
    raise AssertionError('Page image did not load')

if verify_saved:
    expected=int(sys.argv[sys.argv.index('--verify-saved')+1])
    assert js('book.source_page')==expected,(js('book.source_page'),expected)
    ready();print('PASS: fresh process restored PDF page',expected);sys.exit(0)
count=int(js('pages.length'))
expected=int(sys.argv[2]) if len(sys.argv)>2 else 25
assert count==expected,(count,expected)
assert root.findChild(type(root),'pageNavigation') is None
hits=0
for index in range(count):
    js(f'goToPage({index})');ready()
    assert js('book.source_page')==index+1
    assert js('selectedWord')==-1
    assert js('book.words.every(function(w) { return w.boxes.every(function(b) { return b[0]>=view[0] && b[1]>=view[1] && b[0]+b[2]<=view[0]+view[2] && b[1]+b[3]<=view[1]+view[3] }) })'),index
    word=js('book.words.findIndex(function(w) { return !!w.pinyin })')
    if word>=0:
        point=js(f'pageImage.mapToItem(root,(book.words[{word}].boxes[0][0]+book.words[{word}].boxes[0][2]/2)*imageScale,(book.words[{word}].boxes[0][1]+book.words[{word}].boxes[0][3]/2)*imageScale)')
        QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())));QTest.qWait(20)
        assert js('selectedWord')==word,(index,word,js('selectedWord'))
        assert js('popup.visible && popup.pinyin.length>0');hits+=1
    else:assert js('book.words.length')==0

def swipe(dx,dy=0):
    x=int(js('root.width/2'));y=int(js('root.height*.7'))
    QTest.mousePress(view,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
    for step in range(1,7):QTest.mouseMove(view,QPoint(x+round(dx*step/6),y+round(dy*step/6)),15)
    QTest.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,QPoint(x+dx,y+dy));QTest.qWait(80)

js('goToPage(22); showTranslation=true');ready()
swipe(-200);assert js('pageIndex')==23 and js('selectedWord')==-1 and js('showTranslation')
swipe(200);assert js('pageIndex')==22
swipe(10,150);assert js('pageIndex')==22 and js('selectedWord')==-1
swipe(30);assert js('pageIndex')==22 and js('selectedWord')==-1
js('goToPage(0)');ready();swipe(200);assert js('pageIndex')==0
js(f'goToPage({count-1})');ready();swipe(-200);assert js('pageIndex')==count-1
js(f'goToPage({count-2})');ready()
state=Path(os.environ['XDG_DATA_HOME'])/'duchinese-pdf-reader/progress.ini'
assert state.is_file() and f'lastPage={count-1}' in state.read_text()
subprocess.run([sys.executable,__file__,str(root_path),'--verify-saved',str(count-1)],env=os.environ,check=True)
view.grabWindow().save(str(root_path/'preview-swipe-reader.png'))
print(f'PASS: {count} images, {hits} lookup pages; swipe directions, boundaries, vertical/short gesture rejection, no swipe-generated lookup, and disk persistence across processes.')

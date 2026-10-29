#!/usr/bin/env python3
"""Exercise actual overlay/menu QML against a synthetic local processing service."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QResource, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

bundle = Path(sys.argv[1]).resolve()
document = '00000000-0000-4000-8000-000000000001'
state = {'state': 'idle', 'revision': '1', 'total': 1, 'done': 0, 'message': ''}
page = {'width': 2000, 'height': 2800, 'crop': [0, 0, 2000, 2800],
        'words': [{'hanzi': '学习', 'pinyin': 'xué xí', 'meaning': 'study',
                   'sentence': 0, 'boxes': [[200, 200, 100, 50]]}],
        'sentences': [{'text': '学习', 'translation': 'Study.'}]}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, value, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())
    def do_GET(self):
        if '/pages/' in self.path:
            self.reply(page if state['state'] == 'complete' else {},
                       200 if state['state'] == 'complete' else 404)
        else: self.reply(dict(state))
    def do_POST(self):
        assert self.headers.get('X-DuChinese-Local') == '1'
        if self.path.endswith('/cancel'):
            assert state['state'] == 'running'
            state.update(state='cancelling', revision='3', message='Stopping current requests')
        else:
            assert self.path.endswith('/process')
            assert state['state'] in ('idle', 'paused')
            state.update(state='running', revision='2', message='Processing 10 pages in parallel')
        self.reply(dict(state), 202)

server = ThreadingHTTPServer(('127.0.0.1', 9876), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
app = QGuiApplication([])
engine = QQmlEngine()
assert QResource.registerResource(str(bundle))
# The native Ark module exists only inside xochitl; mock its public base API.
with tempfile.TemporaryDirectory() as temporary:
    module = Path(temporary) / 'ark/controls'
    module.mkdir(parents=True)
    (module / 'qmldir').write_text('module ark.controls\nFoldoutItem 1.0 FoldoutItem.qml\n')
    (module / 'FoldoutItem.qml').write_text('''import QtQuick.Controls
Button { property string label; property string description; property string iconSource }
''')
    engine.addImportPath(temporary)
    component = QQmlComponent(engine)
    component.setData(('''import QtQuick
import "qrc:/duchinese-pdf-overlay"
Item {
 id: root
 width: 2000; height: 2800
 property int currentPage: 0
 property var document: ({id: "DOC", redirectionPageMap: [0, -1, 1, 4, 2]})
 Item { id: duchinesePdfOverlay; property alias item: lookup }
 Item { id: sceneView; width: 2000; height: 2800; property rect pageBorderRect: Qt.rect(0,0,2000,2800) }
 LookupOverlay { id: lookup; anchors.fill: parent; nativeSceneView: sceneView; documentId: "DOC"; pageIndex: 0 }
 ProcessMenuItem { id: menu; documentId: "DOC" }
 property alias overlay: lookup
 property alias menu: menu
}'''.replace('DOC', document)).encode(), QUrl('file:///tmp/ProcessingCheck.qml'))
    obj = component.create()
    assert obj, component.errors()
    def evaluate(code):
        expression = QQmlExpression(QQmlEngine.contextForObject(obj), obj, code)
        result = expression.evaluate()
        assert not expression.hasError(), expression.error().toString()
        return result[0] if isinstance(result, tuple) else result
    def until(condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            app.processEvents()
            if condition(): return
            time.sleep(.01)
        raise AssertionError('QML request did not finish')
    until(lambda: evaluate('menu.job.state === "idle" && !menu.serviceError'))
    evaluate('menu.clicked()')
    until(lambda: evaluate('menu.job.state === "running" && !menu.requesting'))
    assert evaluate('menu.enabled && menu.label === "Stop Chinese processing"')
    evaluate('menu.clicked()')
    until(lambda: evaluate('menu.job.state === "cancelling" && !menu.requesting'))
    assert evaluate('!menu.enabled')
    state.update(state='paused', revision='4', message='Stopped. Tap to continue.')
    until(lambda: evaluate('menu.job.state === "paused"'))
    assert evaluate('menu.enabled && menu.label === "Resume Chinese processing"')
    evaluate('menu.clicked()')
    until(lambda: evaluate('menu.job.state === "running" && !menu.requesting'))
    state.update(state='complete', revision='5', done=1, message='Chinese lookup ready')
    until(lambda: evaluate('overlay.pageData !== null && menu.job.state === "complete"'))
    assert evaluate('overlay.hitTest(250,225).word.hanzi === "学习"')
    assert evaluate('!menu.enabled && menu.label === "Chinese lookup ready"')
    evaluate('overlay.pageIndex = 1')
    # No stale word/selection survives a page change while fetching its lookup.
    assert evaluate('overlay.processedPageData === null && overlay.selectedWord === null')
    # Execute the actual native patch's initialization, including its bindings.
    patch = (Path(__file__).resolve().parents[1] /
             'packaging/native-pdf-overlay/document-overlay.qmd.in').read_text()
    initialization = re.search(r'onLoaded: \{(.*?)\n                \}', patch, re.S).group(1)
    evaluate('(function() { var item = overlay; ' + initialization + ' })()')
    assert evaluate('overlay.pageIndex === 0')
    evaluate('root.currentPage = 1')
    assert evaluate('overlay.pageIndex === -1 && overlay.pageData === null')
    evaluate('root.currentPage = 2')
    assert evaluate('overlay.pageIndex === 1')
    evaluate('root.currentPage = 3')
    assert evaluate('overlay.pageIndex === 4')
    evaluate('root.document = ({id: "DOC", redirectionPageMap: [0, 3, 2, 1]})'
             .replace('DOC', document))
    assert evaluate('overlay.pageIndex === 1')
    evaluate('root.currentPage = 99')
    assert evaluate('overlay.pageIndex === -1 && overlay.pageData === null')
    evaluate('root.document = null')
    assert evaluate('overlay.pageIndex === -1 && overlay.documentId === ""')
    obj.deleteLater()
    app.processEvents()
server.shutdown()
print('Native QML: processing, live lookup, page reset, inserted/reordered PDF page mapping passed.')

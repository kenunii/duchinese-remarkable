import QtQuick 2.15
import QtCore
import Qt.labs.settings 1.1
import "Book.js" as Book

Rectangle {
    id: root
    color: "white"
    signal close
    property var pages: typeof Book.pages !== "undefined" ? Book.pages : [Book.book]
    property int pageIndex: 0
    property bool progressReady: false
    property string progressFile: decodeURIComponent(StandardPaths.writableLocation(StandardPaths.GenericDataLocation).toString().replace(/^file:\/\//, "")) + "/duchinese-pdf-reader/progress.ini"
    Settings {
        id: readingState
        fileName: root.progressFile
        category: "pdf-" + (typeof Book.id !== "undefined" ? Book.id : "legacy")
    }
    function saveProgress() {
        if (!progressReady) return
        readingState.setValue("lastPage", book.source_page)
        readingState.sync()
    }
    function restoreProgress() {
        var restored = 0
        var lastPage = Number(readingState.value("lastPage", pages[0].source_page))
        for (var i = 0; i < pages.length; ++i) {
            if (pages[i].source_page <= lastPage) restored = i
        }
        pageIndex = restored
        progressReady = true
    }
    property var book: pages[pageIndex]
    function goToPage(index) {
        if (index < 0 || index >= pages.length) return
        selectedWord = -1
        zoom = 1
        pageIndex = index
        resetView()
        saveProgress()
        console.log("[PDF Reader Test] showing PDF page " + book.source_page)
    }
    property int selectedWord: -1
    property bool showTranslation: false
    property bool fullPage: false
    property real zoom: 1
    readonly property var selected: selectedWord >= 0 ? book.words[selectedWord] : null
    readonly property var view: fullPage ? [0, 0, book.image_width, book.image_height] : book.view
    readonly property real imageScale: Math.min(viewport.width / view[2], viewport.height / view[3]) * zoom
    readonly property real originX: Math.max(0, (viewport.width - view[2] * imageScale) / 2)
    readonly property real originY: Math.max(0, (viewport.height - view[3] * imageScale) / 2)
    FontLoader { id: chineseFont; source: "NotoSansSC.ttf" }

    function resetView() {
        selectedWord = -1
        viewport.contentX = 0
        viewport.contentY = 0
    }

    function hitTest(x, y) {
        var nearest = -1
        var distance = 1e20
        // One coordinate transform drives both rendering and hit testing.
        for (var i = 0; i < book.words.length; ++i) {
            var word = book.words[i]
            if (!word.pinyin) continue
            for (var j = 0; j < word.boxes.length; ++j) {
                var b = word.boxes[j]
                var dx = Math.max(b[0] - x, 0, x - b[0] - b[2])
                var dy = Math.max(b[1] - y, 0, y - b[1] - b[3])
                var d = dx * dx + dy * dy
                if (d < distance && dx <= 7 / imageScale && dy <= 10 / imageScale) {
                    nearest = i
                    distance = d
                }
            }
        }
        return nearest
    }

    function tapPage(x, y) {
        var found = hitTest(x, y)
        selectedWord = found === selectedWord ? -1 : found
        if (selected) {
            var box = selected.boxes[0]
            for (var i = 0; i < selected.boxes.length; ++i) {
                var candidate = selected.boxes[i]
                if (y >= candidate[1] && y <= candidate[1] + candidate[3]) {
                    box = candidate
                    break
                }
            }
            var point = pageImage.mapToItem(root, box[0] * imageScale, box[1] * imageScale)
            popup.wordRect = Qt.rect(point.x, point.y, box[2] * imageScale, box[3] * imageScale)
        }
        if (selectedWord >= 0) console.log("[PDF Reader Test] selected word " + selectedWord)
    }

    SentenceTranslationBar {
        id: translationArea
        objectName: "sentenceTranslationBar"
        anchors.top: parent.top; anchors.topMargin: 20
        anchors.left: parent.left; anchors.leftMargin: 48
        anchors.right: parent.right; anchors.rightMargin: 48
        revealed: root.showTranslation
        hasSelection: root.selected !== null
        translation: root.selected ? root.book.sentences[root.selected.sentence].translation : ""
        onToggleRequested: root.showTranslation = !root.showTranslation
    }

    Flickable {
        id: viewport
        objectName: "pdfViewport"
        anchors.top: translationArea.bottom; anchors.bottom: parent.bottom
        anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 24
        clip: true
        contentWidth: Math.max(width, root.view[2] * root.imageScale)
        contentHeight: Math.max(height, root.view[3] * root.imageScale)
        interactive: root.zoom > 1
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.HorizontalAndVerticalFlick
        onMovementStarted: root.selectedWord = -1

        Image {
            id: pageImage
            objectName: "pdfImage"
            x: root.originX - root.view[0] * root.imageScale
            y: root.originY - root.view[1] * root.imageScale
            width: root.book.image_width * root.imageScale
            height: root.book.image_height * root.imageScale
            source: root.book.image_file || "page.png"
            cache: false
            asynchronous: true
            smooth: true
            fillMode: Image.Stretch
            onStatusChanged: if (status === Image.Ready) console.log("[PDF Reader Test] page ready")
            Repeater {
                model: root.selected ? root.selected.boxes : []
                Rectangle {
                    required property var modelData
                    x: modelData[0] * root.imageScale - 2
                    y: modelData[1] * root.imageScale - 2
                    width: modelData[2] * root.imageScale + 4
                    height: modelData[3] * root.imageScale + 4
                    color: "transparent"
                    border.color: "black"; border.width: 3
                }
            }
            MouseArea {
                anchors.fill: parent
                enabled: root.zoom > 1
                onClicked: (mouse) => root.tapPage(mouse.x / root.imageScale, mouse.y / root.imageScale)
            }
        }
    }

    MouseArea {
        id: pageGesture
        objectName: "pageGesture"
        anchors.fill: viewport
        enabled: root.zoom <= 1
        property real startX: 0
        property real startY: 0
        property real travel: 0
        property bool turned: false
        onPressed: (mouse) => {
            startX = mouse.x; startY = mouse.y; travel = 0; turned = false
        }
        onPositionChanged: (mouse) => {
            if (pressed) travel = Math.max(travel, Math.abs(mouse.x-startX), Math.abs(mouse.y-startY))
        }
        onReleased: (mouse) => {
            var dx = mouse.x-startX, dy = mouse.y-startY
            travel = Math.max(travel, Math.abs(dx), Math.abs(dy))
            if (Math.abs(dx) >= 80 && Math.abs(dx) >= Math.abs(dy)*1.5) {
                turned = true
                root.goToPage(root.pageIndex + (dx < 0 ? 1 : -1))
            }
        }
        onClicked: (mouse) => {
            if (turned || travel > 18) return
            var point = mapToItem(pageImage, mouse.x, mouse.y)
            root.tapPage(point.x/root.imageScale, point.y/root.imageScale)
        }
        onCanceled: { turned = true; travel = 1000 }
    }

    WordPopup {
        id: popup
        objectName: "lookupPopup"
        visible: root.selected !== null
        hanzi: root.selected ? root.selected.hanzi : ""
        pinyin: root.selected ? root.selected.pinyin : ""
        meaning: root.selected ? root.selected.meaning : ""
        textFont: chineseFont.name
        availableRect: Qt.rect(48, viewport.y, root.width - 96, viewport.height)
        onDismissed: root.selectedWord = -1
    }
    Component.onCompleted: {
        restoreProgress()
        console.log("[PDF Reader Test] loaded PDF page " + book.source_page + " of " + pages.length)
    }
    Component.onDestruction: saveProgress()
}

import QtQuick 2.15
import "LookupData.js" as LookupData

Item {
    id: root
    property var nativeSceneView: null
    property string documentId: ""
    property int pageIndex: 0
    property var pageData: LookupData.documents[documentId]
        ? (LookupData.documents[documentId].pages[pageIndex + 1] || null) : null
    property var selectedWord: null
    property var selectedBox: null
    property int selectedSentenceIndex: -1
    property var selectedSentenceLines: []
    readonly property var selectedSentence: pageData && selectedSentenceIndex >= 0
        ? pageData.sentences[selectedSentenceIndex] : null
    visible: pageData !== null

    onPageDataChanged: {
        selectedWord = null
        selectedBox = null
        selectedSentenceIndex = -1
        selectedSentenceLines = []
    }

    FontLoader {
        id: chineseFont
        source: "qrc:/duchinese-pdf-overlay/NotoSansSC.ttf"
    }

    function boxRect(box) {
        if (!nativeSceneView || !pageData || !box) return Qt.rect(0, 0, 0, 0)
        var bounds = nativeSceneView.pageBorderRect
        var crop = pageData.crop
        return Qt.rect(
            pageTouchLayer.x + bounds.x + (box[0] - crop[0]) * bounds.width / crop[2],
            pageTouchLayer.y + bounds.y + (box[1] - crop[1]) * bounds.height / crop[3],
            box[2] * bounds.width / crop[2],
            box[3] * bounds.height / crop[3])
    }

    function hitTest(viewX, viewY) {
        if (!nativeSceneView || !pageData) return null
        var bounds = nativeSceneView.pageBorderRect
        if (!bounds || bounds.width <= 0 || bounds.height <= 0) return null
        // xochitl shows the PDF CropBox, while OCR coordinates cover its MediaBox.
        // pageBorderRect already includes native zoom and pan in view coordinates.
        var crop = pageData.crop
        var x = crop[0] + (viewX - bounds.x) * crop[2] / bounds.width
        var y = crop[1] + (viewY - bounds.y) * crop[3] / bounds.height
        if (x < 0 || y < 0 || x > pageData.width || y > pageData.height) return null
        var nearest = null
        var nearestBox = null
        var distance = 1e20
        for (var i = 0; i < pageData.words.length; ++i) {
            var word = pageData.words[i]
            for (var j = 0; j < word.boxes.length; ++j) {
                var b = word.boxes[j]
                var dx = Math.max(b[0] - x, 0, x - b[0] - b[2])
                var dy = Math.max(b[1] - y, 0, y - b[1] - b[3])
                var d = dx * dx + dy * dy
                if (d < distance && dx <= 18 && dy <= 18) {
                    nearest = word
                    nearestBox = b
                    distance = d
                }
            }
        }
        return nearest ? {word: nearest, box: nearestBox} : null
    }

    function sentenceLines(index) {
        var lines = []
        for (var i = 0; i < pageData.words.length; ++i) {
            var word = pageData.words[i]
            if (word.sentence !== index) continue
            for (var j = 0; j < word.boxes.length; ++j) {
                var box = word.boxes[j]
                var centerY = box[1] + box[3] / 2
                var line = null
                for (var k = 0; k < lines.length; ++k) {
                    var candidate = lines[k]
                    if (Math.abs(candidate.centerY - centerY) < Math.max(candidate.h, box[3]) / 2) {
                        line = candidate
                        break
                    }
                }
                if (line) {
                    var right = Math.max(line.x + line.w, box[0] + box[2])
                    var bottom = Math.max(line.y + line.h, box[1] + box[3])
                    line.x = Math.min(line.x, box[0])
                    line.y = Math.min(line.y, box[1])
                    line.w = right - line.x
                    line.h = bottom - line.y
                    line.centerY = line.y + line.h / 2
                } else {
                    lines.push({x: box[0], y: box[1], w: box[2], h: box[3], centerY: centerY})
                }
            }
        }
        return lines.map(function(line) { return [line.x, line.y, line.w, line.h] })
    }

    function selectSentence(match) {
        if (!match || !pageData) return
        var index = match.word.sentence
        if (index < 0 || index >= pageData.sentences.length) return
        selectedWord = null
        selectedBox = match.box
        selectedSentenceLines = sentenceLines(index)
        selectedSentenceIndex = index
    }

    function insidePopup(viewX, viewY) {
        var wordPoint = popup.mapFromItem(pageTouchLayer, viewX, viewY)
        if (popup.visible && wordPoint.x >= 0 && wordPoint.x < popup.width
            && wordPoint.y >= 0 && wordPoint.y < popup.height) return true
        var sentencePoint = sentencePopup.mapFromItem(pageTouchLayer, viewX, viewY)
        return sentencePopup.visible && sentencePoint.x >= 0 && sentencePoint.x < sentencePopup.width
            && sentencePoint.y >= 0 && sentencePoint.y < sentencePopup.height
    }

    Item {
        id: pageTouchLayer
        visible: root.nativeSceneView !== null
        x: visible ? root.nativeSceneView.mapToItem(root, 0, 0).x : 0
        y: visible ? root.nativeSceneView.mapToItem(root, 0, 0).y : 0
        width: visible ? root.nativeSceneView.width : 0
        height: visible ? root.nativeSceneView.height : 0
        TapHandler {
            id: pageTap
            acceptedDevices: PointerDevice.TouchScreen
            gesturePolicy: TapHandler.DragThreshold
            onTapped: (point) => {
                if (root.insidePopup(point.position.x, point.position.y)) return
                var match = root.hitTest(point.position.x, point.position.y)
                root.selectedWord = match ? match.word : null
                root.selectedBox = match ? match.box : null
                root.selectedSentenceIndex = -1
                root.selectedSentenceLines = []
            }
            onLongPressed: {
                if (root.insidePopup(point.position.x, point.position.y)) return
                var match = root.hitTest(point.position.x, point.position.y)
                root.selectSentence(match)
            }
        }
    }

    Repeater {
        model: root.selectedWord ? root.selectedWord.boxes : root.selectedSentenceLines
        Rectangle {
            required property var modelData
            readonly property rect mappedBox: root.boxRect(modelData)
            x: mappedBox.x - 3
            y: mappedBox.y - 3
            width: mappedBox.width + 6
            height: mappedBox.height + 6
            color: "transparent"
            border.color: "black"
            border.width: root.selectedSentence ? 2 : 3
            z: 4
        }
    }

    WordPopup {
        id: popup
        visible: root.selectedWord !== null
        hanzi: root.selectedWord ? root.selectedWord.hanzi : ""
        pinyin: root.selectedWord ? root.selectedWord.pinyin : ""
        meaning: root.selectedWord ? root.selectedWord.meaning : ""
        textFont: chineseFont.name
        wordRect: root.boxRect(root.selectedBox)
        availableRect: Qt.rect(20, 20, root.width - 40, root.height - 40)
        onDismissed: {
            root.selectedWord = null
            root.selectedBox = null
        }
    }

    SentencePopup {
        id: sentencePopup
        visible: root.selectedSentence !== null
        sourceText: root.selectedSentence ? root.selectedSentence.text : ""
        translation: root.selectedSentence ? root.selectedSentence.translation : ""
        textFont: chineseFont.name
        wordRect: root.boxRect(root.selectedBox)
        availableRect: Qt.rect(20, 20, root.width - 40, root.height - 40)
        onDismissed: {
            root.selectedSentenceIndex = -1
            root.selectedSentenceLines = []
            root.selectedBox = null
        }
    }
}

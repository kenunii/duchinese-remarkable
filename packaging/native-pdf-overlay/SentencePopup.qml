import QtQuick 2.15

Rectangle {
    id: popup
    property string sourceText: ""
    property string translation: ""
    property string textFont: "Noto Sans"
    property rect wordRect: Qt.rect(0, 0, 0, 0)
    property rect availableRect: Qt.rect(20, 20, 1000, 1600)
    signal dismissed

    width: Math.min(850, availableRect.width)
    height: Math.min(availableRect.height, Math.max(210, Math.min(480, label.implicitHeight + 44)))
    x: Math.max(availableRect.x, Math.min(availableRect.x + availableRect.width - width,
                                       wordRect.x + wordRect.width / 2 - width / 2))
    y: {
        var below = wordRect.y + wordRect.height + 10
        var above = wordRect.y - height - 10
        var preferred = below + height <= availableRect.y + availableRect.height ? below : above
        return Math.max(availableRect.y, Math.min(availableRect.y + availableRect.height - height, preferred))
    }
    z: 20
    color: "white"
    border.color: "black"
    border.width: 3

    Flickable {
        id: viewport
        anchors.fill: parent
        anchors.margins: 22
        contentWidth: width
        contentHeight: Math.max(height, label.implicitHeight)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Text {
            id: label
            width: viewport.width
            text: popup.sourceText + "\n" + (popup.translation || "No sentence translation available")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            font.family: popup.textFont
            font.pixelSize: 26
        }
    }
    TapHandler {
        gesturePolicy: TapHandler.DragThreshold
        onTapped: popup.dismissed()
    }
}

import QtQuick 2.15

Rectangle {
    id: popup
    property string hanzi: ""
    property string pinyin: ""
    property string meaning: ""
    property string textFont: "Noto Sans"
    property rect wordRect: Qt.rect(0, 0, 0, 0)
    property rect availableRect: Qt.rect(48, 0, 620, 1000)
    signal dismissed

    width: Math.min(620, availableRect.width)
    height: Math.min(availableRect.height, Math.max(180, label.implicitHeight + 44))
    x: Math.max(availableRect.x, Math.min(availableRect.x + availableRect.width - width,
                                       wordRect.x + wordRect.width / 2 - width / 2))
    y: {
        var below = wordRect.y + wordRect.height + 10
        var above = wordRect.y - height - 10
        var preferred = below + height <= availableRect.y + availableRect.height ? below : above
        return Math.max(availableRect.y, Math.min(availableRect.y + availableRect.height - height, preferred))
    }
    z: 20
    color: "white"; border.width: 3; border.color: "black"
    Text {
        id: label
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        anchors.margins: 22
        text: popup.hanzi + "   " + popup.pinyin + "\n" + popup.meaning
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        font.family: popup.textFont; font.pixelSize: 25
    }
    MouseArea { anchors.fill: parent; onClicked: popup.dismissed() }
}

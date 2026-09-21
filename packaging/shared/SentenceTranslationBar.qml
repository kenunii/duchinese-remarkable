import QtQuick 2.15

Rectangle {
    id: bar
    property bool revealed: false
    property bool hasSelection: false
    property string translation: ""
    signal toggleRequested
    height: 116
    color: "white"; border.width: 2; border.color: "black"
    Flickable {
        id: textViewport
        anchors.fill: parent; anchors.margins: 16
        contentWidth: width
        contentHeight: Math.max(height, label.implicitHeight)
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        Text {
            id: label
            width: textViewport.width
            y: Math.max(0, (textViewport.height - implicitHeight) / 2)
            text: !bar.revealed ? "Tap to show sentence translation" :
                  !bar.hasSelection ? "Select a word to show its sentence translation" :
                  (bar.translation || "No sentence translation available")
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            font.family: "Noto Sans"; font.pixelSize: 23
            color: bar.revealed ? "black" : "#555"
            onTextChanged: textViewport.contentY = 0
        }
        MouseArea {
            width: textViewport.width; height: textViewport.contentHeight
            onClicked: bar.toggleRequested()
        }
    }
}

import QtQuick
import QtQuick.Window

Window {
    id: root
    width: Screen.width
    height: Screen.height
    visible: true
    color: "white"
    title: "DuChinese Reader Probe"

    property int selectedWord: -1

    Timer {
        interval: 180000
        running: true
        repeat: false
        onTriggered: Qt.quit()
    }

    readonly property var words: [
        { hanzi: "我", pinyin: "wǒ", meaning: "I; me" },
        { hanzi: "今天", pinyin: "jīntiān", meaning: "today" },
        { hanzi: "坐", pinyin: "zuò", meaning: "to ride; to sit" },
        { hanzi: "地铁", pinyin: "dìtiě", meaning: "subway; metro" },
        { hanzi: "去", pinyin: "qù", meaning: "to go" },
        { hanzi: "上班", pinyin: "shàngbān", meaning: "to go to work" }
    ]

    Text {
        id: heading
        x: 72
        y: 80
        text: "阅读测试"
        color: "black"
        font.pixelSize: 44
        font.bold: true
    }

    Flow {
        id: sentence
        x: 72
        y: 190
        width: root.width - 144
        spacing: 6

        Repeater {
            model: root.words

            Rectangle {
                required property int index
                required property var modelData
                width: wordText.implicitWidth + 14
                height: 76
                color: root.selectedWord === index ? "#dddddd" : "white"
                border.width: root.selectedWord === index ? 2 : 0
                border.color: "black"

                Text {
                    id: wordText
                    anchors.centerIn: parent
                    text: modelData.hanzi
                    color: "black"
                    font.pixelSize: 50
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.selectedWord = index
                }
            }
        }

        Text {
            height: 76
            verticalAlignment: Text.AlignVCenter
            text: "。"
            color: "black"
            font.pixelSize: 50
        }
    }

    Rectangle {
        id: lookup
        visible: root.selectedWord >= 0
        x: 72
        y: 380
        width: root.width - 144
        height: 250
        color: "white"
        border.width: 3
        border.color: "black"

        Text {
            anchors.fill: parent
            anchors.margins: 30
            text: root.selectedWord < 0 ? "" :
                root.words[root.selectedWord].hanzi + "\n" +
                root.words[root.selectedWord].pinyin + "\n" +
                root.words[root.selectedWord].meaning
            color: "black"
            font.pixelSize: 36
            lineHeight: 1.25
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.selectedWord = -1
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: 72
        anchors.right: parent.right
        anchors.rightMargin: 72
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40
        height: 80
        color: "white"
        border.width: 2
        border.color: "black"

        Text {
            anchors.centerIn: parent
            text: "Tap words · tap here to exit"
            color: "black"
            font.pixelSize: 24
        }

        MouseArea {
            anchors.fill: parent
            onClicked: Qt.quit()
        }
    }
}

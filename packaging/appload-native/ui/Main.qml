import QtQuick 2.15
import net.asivery.ApploadUtils

Rectangle {
    id: root
    anchors.fill: parent
    color: "white"

    signal close
    function unloading() {}

    property int selectedWord: -1
    readonly property var words: [
        { hanzi: "我", pinyin: "wǒ", meaning: "I; me" },
        { hanzi: "今天", pinyin: "jīntiān", meaning: "today" },
        { hanzi: "坐", pinyin: "zuò", meaning: "to ride; to sit" },
        { hanzi: "地铁", pinyin: "dìtiě", meaning: "subway; metro" },
        { hanzi: "去", pinyin: "qù", meaning: "to go" },
        { hanzi: "上班", pinyin: "shàngbān", meaning: "to go to work" }
    ]

    FontLoader {
        id: chineseFont
        source: "qrc:/fonts/NotoSansSC.ttf"
    }

    DisplayMethodArea {
        anchors.fill: parent
        displayMethod: DisplayMethodArea.Direct
    }

    Text {
        x: 72
        y: 80
        text: "阅读测试"
        color: "black"
        font.family: chineseFont.name
        font.pixelSize: 44
        font.bold: true
    }

    Flow {
        x: 72
        y: 190
        width: root.width - 144
        spacing: 6

        Repeater {
            model: root.words

            Rectangle {
                property int wordIndex: index
                width: wordText.implicitWidth + 14
                height: 76
                color: root.selectedWord === wordIndex ? "#dddddd" : "white"
                border.width: root.selectedWord === wordIndex ? 2 : 0
                border.color: "black"

                Text {
                    id: wordText
                    anchors.centerIn: parent
                    text: modelData.hanzi
                    color: "black"
                    font.family: chineseFont.name
                    font.pixelSize: 50
                }

                MouseArea {
                    anchors.fill: parent
                    onClicked: root.selectedWord = wordIndex
                }
            }
        }

        Text {
            height: 76
            verticalAlignment: Text.AlignVCenter
            text: "。"
            color: "black"
            font.family: chineseFont.name
            font.pixelSize: 50
        }
    }

    Rectangle {
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
            font.family: chineseFont.name
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
            onClicked: root.close()
        }
    }
}

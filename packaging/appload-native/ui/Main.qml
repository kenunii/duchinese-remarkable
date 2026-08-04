import QtQuick 2.15
import net.asivery.ApploadUtils
import net.asivery.AppLoad 1.0

Rectangle {
    id: root
    anchors.fill: parent
    color: "white"

    signal close
    function unloading() { endpoint.terminate() }

    property string screen: "library"
    property string heading: "DuChinese"
    property string statusText: "Starting…"
    property string listingKind: "top"
    property bool busy: true
    property var words: []
    property var sentenceEnds: []
    property var translations: []
    property int page: 0
    property int wordsPerPage: 36
    property int selectedWord: -1
    property bool showPinyin: false
    property string levelFilter: ""
    property var listingPayload: null
    property var previousListingPayload: null
    property string previousListingKind: "top"
    readonly property var levelFilters: ["", "newbie", "elementary", "intermediate", "upper intermediate", "advanced", "master"]

    FontLoader { id: chineseFont; source: "qrc:/fonts/NotoSansSC.ttf" }
    DisplayMethodArea { anchors.fill: parent; displayMethod: DisplayMethodArea.Fast }

    ListModel { id: lessonModel }

    function send(type, value) {
        busy = true
        statusText = "Loading…"
        endpoint.sendMessage(type, JSON.stringify(value || {}))
    }

    function addItems(value, seen) {
        if (!value || typeof value !== "object") return
        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; ++i) addItems(value[i], seen)
            return
        }
        var title = value.title || value.name
        var lessonPath = value.path || value.canonical_path
        var coursePath = value.lessons_url || value.course_path
        if (title && (lessonPath || coursePath)) {
            var path = lessonPath || coursePath
            var isCourse = !value.crd_url && (value.lessons_url || value.course_path ||
                (String(path).indexOf("/courses/") >= 0 && String(path).indexOf("/lessons/") !== 0))
            if (isCourse && String(path).slice(-13) !== "/lessons.json")
                path = String(path).replace(/\/$/, "") + "/lessons.json"
            var key = (isCourse ? "c:" : "l:") + path
            var levels = value.level ? [String(value.level).toLowerCase()] : (value.levels || [])
            var matchesLevel = !root.levelFilter
            for (var levelIndex = 0; levelIndex < levels.length; ++levelIndex)
                if (String(levels[levelIndex]).toLowerCase() === root.levelFilter) matchesLevel = true
            if (!seen[key] && matchesLevel) {
                seen[key] = true
                var displayTitle = String(title)
                var chapterLabel = ""
                if (!isCourse && value.course_position !== undefined && value.course_position !== null) {
                    chapterLabel = "Chapter " + (Number(value.course_position) + 1)
                    displayTitle = chapterLabel + " · " + displayTitle
                }
                lessonModel.append({
                    itemTitle: displayTitle,
                    itemSubtitle: String(value.level || value.course_type || value.synopsis || ""),
                    itemPath: String(path),
                    itemCourse: isCourse,
                    itemLocked: value.locked === true
                })
            }
            if (lessonPath || value.crd_url) return
        }
        for (var keyName in value) {
            if (keyName !== "words" && keyName !== "syllable_times")
                addItems(value[keyName], seen)
        }
    }

    function showListing(kind, payload) {
        listingPayload = payload
        listingKind = kind
        lessonModel.clear()
        addItems(payload, {})
        heading = kind === "search" ? "Search results" :
                  kind === "latest" ? "Latest stories" :
                  kind === "course" && payload.lessons && payload.lessons.length ?
                      (payload.lessons[0].course_title || "Course") : "Featured"
        screen = "library"
        statusText = lessonModel.count ? "" : "No stories found"
    }

    function openItem(isCourse, path) {
        if (isCourse) {
            previousListingPayload = listingPayload
            previousListingKind = listingKind
        }
        send(isCourse ? 6 : 5, { path: path })
    }

    function backToBooks() {
        if (previousListingPayload) showListing(previousListingKind, previousListingPayload)
    }

    function cycleLevelFilter() {
        var index = levelFilters.indexOf(levelFilter)
        levelFilter = levelFilters[(index + 1) % levelFilters.length]
        if (listingPayload) {
            lessonModel.clear()
            addItems(listingPayload, {})
            statusText = lessonModel.count ? "" : "No stories at this level"
        }
    }

    function filterLabel() {
        if (!levelFilter) return "Level: All"
        return "Level: " + levelFilter.replace(/(^| )[a-z]/g, function(match) { return match.toUpperCase() })
    }

    function showLesson(payload) {
        var lesson = payload.lesson || {}
        var reader = payload.reader || {}
        words = reader.words || []
        sentenceEnds = reader.sentence_indices || []
        translations = reader.sentence_translations || []
        heading = lesson.title || "Story"
        page = 0
        selectedWord = -1
        screen = "reader"
        statusText = words.length ? "" : "This story contains no words"
    }

    function receive(type, contents) {
        busy = false
        var data
        try { data = JSON.parse(String(contents)) }
        catch (error) { statusText = "Invalid backend response"; return }
        if (type === 101) {
            if (data.authenticated) send(2, {})
            else statusText = "Login required — import your browser session and reinstall"
        } else if (type === 102) {
            if (data.kind === "lesson") showLesson(data.payload)
            else showListing(data.kind, data.payload)
        } else if (type === 199) {
            statusText = data.message || "Request failed"
        }
    }

    function wordText(word) { return word.tc_hanzi || word.hanzi || "" }
    function selectedTranslation() {
        if (selectedWord < 0) return ""
        for (var i = 0; i < sentenceEnds.length; ++i)
            if (selectedWord < Number(sentenceEnds[i])) return translations[i] || ""
        return ""
    }

    AppLoad {
        id: endpoint
        applicationID: "duchinese-remarkable"
        onMessageReceived: (type, contents) => root.receive(type, contents)
    }

    Component.onCompleted: send(1, {})

    Rectangle {
        id: toolbar
        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
        height: 108
        color: "white"
        border.width: 0

        Rectangle {
            id: booksBackButton
            visible: root.screen === "library" && root.listingKind === "course"
            anchors.left: parent.left; anchors.leftMargin: 30
            anchors.verticalCenter: parent.verticalCenter
            width: 142; height: 66
            color: "white"; border.width: 2; border.color: "black"
            Text { anchors.centerIn: parent; text: "‹ Books"; font.pixelSize: 22 }
            MouseArea { anchors.fill: parent; onClicked: root.backToBooks() }
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: booksBackButton.visible ? 194 : 44
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 360
            text: root.heading
            elide: Text.ElideRight
            color: "black"
            font.family: chineseFont.name
            font.pixelSize: 36
            font.bold: true
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: 44
            anchors.verticalCenter: parent.verticalCenter
            text: "×"
            font.pixelSize: 52
            MouseArea { anchors.fill: parent; anchors.margins: -28; onClicked: root.close() }
        }
        Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 2; color: "black" }
    }

    Row {
        id: navigation
        visible: root.screen === "library"
        anchors.top: toolbar.bottom; anchors.left: parent.left; anchors.right: parent.right
        anchors.margins: 28
        height: 72
        spacing: 14

        Repeater {
            model: [ { label: "Featured", type: 2 }, { label: "Latest", type: 3 } ]
            Rectangle {
                width: 170; height: 68; color: "white"; border.width: 2; border.color: "black"
                Text { anchors.centerIn: parent; text: modelData.label; font.pixelSize: 22 }
                MouseArea { anchors.fill: parent; onClicked: root.send(modelData.type, {}) }
            }
        }
        Rectangle {
            width: 190; height: 68; color: root.levelFilter ? "black" : "white"
            border.width: 2; border.color: "black"
            Text {
                anchors.centerIn: parent
                text: root.filterLabel()
                color: root.levelFilter ? "white" : "black"
                font.pixelSize: 19
            }
            MouseArea { anchors.fill: parent; onClicked: root.cycleLevelFilter() }
        }
        Rectangle {
            width: navigation.width - 170 * 2 - 190 - 110 - 14 * 4; height: 68
            color: "white"; border.width: 2; border.color: "black"
            TextInput {
                id: searchInput
                anchors.fill: parent; anchors.margins: 14
                font.pixelSize: 22
                clip: true
                text: ""
            }
            Text { visible: !searchInput.text && !searchInput.activeFocus; anchors.verticalCenter: parent.verticalCenter; x: 14; text: "Search stories…"; color: "#666"; font.pixelSize: 22 }
        }
        Rectangle {
            width: 110; height: 68; color: "black"
            Text { anchors.centerIn: parent; text: "Search"; color: "white"; font.pixelSize: 20 }
            MouseArea { anchors.fill: parent; onClicked: root.send(4, { query: searchInput.text }) }
        }
    }

    ListView {
        visible: root.screen === "library"
        anchors.top: navigation.bottom; anchors.topMargin: 18
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: status.top
        anchors.leftMargin: 32; anchors.rightMargin: 32
        clip: true
        spacing: 10
        model: lessonModel
        delegate: Rectangle {
            width: ListView.view.width; height: 112
            color: itemLocked ? "#eeeeee" : "white"
            border.width: 2; border.color: "black"
            Text {
                x: 22; y: 16; width: parent.width - 110
                text: itemTitle
                elide: Text.ElideRight
                font.family: chineseFont.name; font.pixelSize: 29; font.bold: true
            }
            Text {
                x: 22; y: 65; width: parent.width - 110
                text: itemLocked ? "Locked" : (itemCourse ? "Course · " : "") + itemSubtitle
                elide: Text.ElideRight; font.pixelSize: 19; color: "#444"
            }
            Text { anchors.right: parent.right; anchors.rightMargin: 26; anchors.verticalCenter: parent.verticalCenter; text: itemCourse ? "›" : "读"; font.family: chineseFont.name; font.pixelSize: 36 }
            MouseArea {
                anchors.fill: parent
                enabled: !itemLocked
                onClicked: root.openItem(itemCourse, itemPath)
            }
        }
    }

    Flow {
        id: wordFlow
        visible: root.screen === "reader"
        anchors.top: toolbar.bottom; anchors.topMargin: 38
        anchors.left: parent.left; anchors.leftMargin: 48
        anchors.right: parent.right; anchors.rightMargin: 48
        height: root.height - 500
        spacing: 5

        Repeater {
            model: root.words.slice(root.page * root.wordsPerPage, (root.page + 1) * root.wordsPerPage)
            Rectangle {
                property int absoluteIndex: root.page * root.wordsPerPage + index
                width: tokenColumn.width + 14
                height: root.showPinyin ? 84 : 65
                color: root.selectedWord === absoluteIndex ? "#dddddd" : "white"
                border.width: root.selectedWord === absoluteIndex ? 2 : 0
                Column {
                    id: tokenColumn
                    anchors.centerIn: parent
                    Text { visible: root.showPinyin; anchors.horizontalCenter: parent.horizontalCenter; text: modelData.pinyin || " "; font.pixelSize: 17 }
                    Text { text: root.wordText(modelData); font.family: chineseFont.name; font.pixelSize: 42; color: "black" }
                }
                MouseArea { anchors.fill: parent; onClicked: root.selectedWord = absoluteIndex }
            }
        }
    }

    Rectangle {
        visible: root.screen === "reader" && root.selectedWord >= 0
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: readerNav.top
        anchors.leftMargin: 48; anchors.rightMargin: 48; anchors.bottomMargin: 18
        height: 220; color: "white"; border.width: 3; border.color: "black"
        Text {
            anchors.fill: parent; anchors.margins: 22
            text: root.selectedWord < 0 ? "" :
                root.wordText(root.words[root.selectedWord]) + "   " + (root.words[root.selectedWord].pinyin || "") + "\n" +
                (root.words[root.selectedWord].meaning || "") + "\n" + root.selectedTranslation()
            wrapMode: Text.Wrap; font.family: chineseFont.name; font.pixelSize: 25
        }
        MouseArea { anchors.fill: parent; onClicked: root.selectedWord = -1 }
    }

    Row {
        id: readerNav
        visible: root.screen === "reader"
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: status.top
        anchors.leftMargin: 48; anchors.rightMargin: 48; height: 70; spacing: 12
        Repeater {
            model: [
                { label: "‹ Back", action: "back" },
                { label: root.showPinyin ? "Hide pinyin" : "Show pinyin", action: "pinyin" },
                { label: (root.page + 1) + " / " + Math.max(1, Math.ceil(root.words.length / root.wordsPerPage)), action: "none" },
                { label: "Next ›", action: "next" }
            ]
            Rectangle {
                width: (readerNav.width - 36) / 4; height: 66; color: "white"; border.width: 2; border.color: "black"
                Text { anchors.centerIn: parent; text: modelData.label; font.pixelSize: 20 }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        root.selectedWord = -1
                        if (modelData.action === "back") {
                            if (root.page > 0) root.page--
                            else root.send(2, {})
                        } else if (modelData.action === "next" && (root.page + 1) * root.wordsPerPage < root.words.length) root.page++
                        else if (modelData.action === "pinyin") root.showPinyin = !root.showPinyin
                    }
                }
            }
        }
    }

    Text {
        id: status
        anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
        height: 62; verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter
        text: root.busy ? "Loading…" : root.statusText
        color: "#333"; font.pixelSize: 19; wrapMode: Text.Wrap
    }
}

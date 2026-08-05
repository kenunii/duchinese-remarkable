import QtQuick 2.15
import net.asivery.ApploadUtils
import net.asivery.AppLoad 1.0
import "Protocol.js" as Protocol

Rectangle {
    id: root
    anchors.fill: parent
    color: "white"

    signal close
    function unloading() {}

    property string screen: "library"
    property string heading: "DuChinese"
    property string readerChapterTitle: ""
    property string statusText: "Starting…"
    property string listingKind: "top"
    property bool busy: true
    property var words: []
    property var sentenceEnds: []
    property var translations: []
    property int page: 0
    property var pageStarts: [0, 0]
    property int selectedWord: -1
    property real lookupX: 48
    property real lookupY: 300
    property bool showPinyin: false
    property bool showSentenceTranslation: false
    property real swipeStartX: 0
    property real swipeStartY: 0
    property bool swipeHandled: false
    property string levelFilter: ""
    property var listingPayload: null
    property var booksContext: ({ payload: null, kind: "top" })
    property var courseContext: ({ path: "", title: "" })
    property var readerReturn: ({ payload: null, kind: "top", coursePath: "" })
    property var readingProgress: ({ entries: {} })
    property var remoteStudied: ({})
    property var activeLesson: null
    readonly property var levelFilters: ["", "newbie", "elementary", "intermediate", "upper intermediate", "advanced", "master"]

    FontLoader { id: chineseFont; source: "qrc:/fonts/NotoSansSC.ttf" }
    Text { id: hanziMeasure; visible: false; font.family: chineseFont.name; font.pixelSize: 42 }
    Text { id: pinyinMeasure; visible: false; font.pixelSize: 17 }
    DisplayMethodArea { anchors.fill: parent; displayMethod: DisplayMethodArea.Fast }

    ListModel { id: lessonModel }

    function send(type, value) {
        busy = true
        statusText = "Loading…"
        sendBackground(type, value)
    }

    function sendBackground(type, value) {
        endpoint.sendMessage(type, JSON.stringify(value || {}))
    }

    function refreshListing(emptyMessage) {
        lessonModel.clear()
        addItems(listingPayload, {})
        statusText = lessonModel.count ? "" : emptyMessage
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
            var isCourse = !value.crd_url && Boolean(value.lessons_url || value.course_path ||
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
                var savedProgress = root.readingProgress.entries ?
                    root.readingProgress.entries[String(path)] : undefined
                var isRemoteRead = !isCourse && root.remoteStudied[String(value.id || "")] === true
                lessonModel.append({
                    itemTitle: displayTitle,
                    itemSubtitle: String(value.level || value.course_type || value.synopsis || ""),
                    itemPath: String(path),
                    itemRawTitle: String(title),
                    itemLevel: String(value.level || ""),
                    itemID: String(value.id || ""),
                    itemChapterLabel: chapterLabel,
                    itemCourse: isCourse,
                    itemLocked: value.locked === true,
                    itemStarted: !isCourse && (savedProgress !== undefined || isRemoteRead),
                    itemRead: isRemoteRead
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
        var courseTitle = kind === "course" && payload.lessons && payload.lessons.length ?
            (payload.lessons[0].course_title || "Course") : ""
        heading = kind === "search" ? "Search results" :
                  kind === "latest" ? "Latest stories" :
                  kind === "course" ? courseTitle : "Featured"
        if (kind !== "course") {
            courseContext = { path: "", title: "" }
        } else courseContext = { path: courseContext.path, title: courseTitle }
        refreshListing("No stories found")
        screen = "library"
    }

    function openItem(isCourse, path, title, level, id, chapterLabel) {
        if (isCourse) {
            booksContext = { payload: listingPayload, kind: listingKind }
            courseContext = { path: path, title: title }
        }
        if (!isCourse) {
            readerReturn = {
                payload: listingPayload,
                kind: listingKind,
                coursePath: listingKind === "course" ? courseContext.path : ""
            }
            activeLesson = { path: path, title: title, level: level, id: id,
                             coursePath: readerReturn.coursePath,
                             courseTitle: courseContext.title,
                             chapterLabel: chapterLabel || "" }
        }
        send(isCourse ? Protocol.course : Protocol.lesson, { path: path })
    }

    function backToBooks() {
        if (booksContext.payload) showListing(booksContext.kind, booksContext.payload)
    }

    function backFromReader() {
        if (readerReturn.coursePath) send(Protocol.course, { path: readerReturn.coursePath })
        else if (readerReturn.payload) showListing(readerReturn.kind, readerReturn.payload)
        else send(Protocol.top, {})
    }

    function cycleLevelFilter() {
        var index = levelFilters.indexOf(levelFilter)
        levelFilter = levelFilters[(index + 1) % levelFilters.length]
        sendBackground(Protocol.settings, { level: levelFilter })
        if (listingPayload) {
            refreshListing("No stories at this level")
        }
    }

    function filterLabel() {
        if (!levelFilter) return "Level: All"
        return "Level: " + levelFilter.replace(/(^| )[a-z]/g, function(match) { return match.toUpperCase() })
    }

    function showLesson(payload) {
        var lesson = payload.lesson || {}
        var reader = payload.reader || {}
        if (activeLesson) {
            if (!activeLesson.id && lesson.id) activeLesson.id = String(lesson.id)
            if (!activeLesson.courseTitle && lesson.course_title)
                activeLesson.courseTitle = String(lesson.course_title)
            if (!activeLesson.chapterLabel && lesson.course_position !== undefined &&
                    lesson.course_position !== null)
                activeLesson.chapterLabel = "Chapter " + (Number(lesson.course_position) + 1)
            if (!activeLesson.coursePath) {
                var lessonCoursePath = lesson.lessons_url || lesson.course_path || ""
                if (lessonCoursePath && String(lessonCoursePath).slice(-13) !== "/lessons.json")
                    lessonCoursePath = String(lessonCoursePath).replace(/\/$/, "") + "/lessons.json"
                activeLesson.coursePath = String(lessonCoursePath)
            }
            if (!readerReturn.coursePath && activeLesson.coursePath)
                readerReturn = { payload: readerReturn.payload, kind: readerReturn.kind,
                                 coursePath: activeLesson.coursePath }
        }
        words = reader.words || []
        sentenceEnds = reader.sentence_indices || []
        translations = reader.sentence_translations || []
        var bookTitle = (activeLesson && activeLesson.courseTitle) || lesson.course_title || ""
        var chapterTitle = lesson.title || (activeLesson && activeLesson.title) || ""
        heading = bookTitle || chapterTitle || "Story"
        readerChapterTitle = bookTitle ?
            ((activeLesson && activeLesson.chapterLabel) ||
             (chapterTitle !== bookTitle ? chapterTitle : "")) : ""
        page = 0
        var saved = activeLesson && readingProgress.entries ? readingProgress.entries[activeLesson.path] : null
        var resumePosition = saved && saved.position !== undefined ? saved.position : 0
        selectedWord = -1
        showSentenceTranslation = false
        screen = "reader"
        statusText = words.length ? "" : "This story contains no words"
        Qt.callLater(function() {
            rebuildPagination(resumePosition)
            saveProgress(words.length > 0 && isLastPage())
        })
    }

    function saveProgress(completed) {
        if (!activeLesson) return
        var existing = readingProgress.entries ? readingProgress.entries[activeLesson.path] : null
        sendBackground(Protocol.progress, {
            path: activeLesson.path,
            id: activeLesson.id || "",
            title: activeLesson.title,
            level: activeLesson.level,
            course_path: activeLesson.coursePath || "",
            course_title: activeLesson.courseTitle || "",
            chapter_label: activeLesson.chapterLabel || "",
            page: page,
            position: currentPageStart(),
            completed: completed || (existing && existing.completed === true)
        })
    }

    function markRemoteRead() {
        if (!activeLesson || !activeLesson.id || remoteStudied[activeLesson.id] === true) return
        sendBackground(Protocol.markRead, { id: activeLesson.id })
    }

    function continueReading() {
        if (!readingProgress.last) return
        var last = readingProgress.last
        readerReturn = { payload: listingPayload, kind: listingKind,
                         coursePath: last.course_path || "" }
        activeLesson = { path: last.path, title: last.title, level: last.level || "",
                         id: last.id || "", coursePath: last.course_path || "",
                         courseTitle: last.course_title || "",
                         chapterLabel: last.chapter_label || "" }
        send(Protocol.lesson, { path: last.path })
    }

    function receive(type, contents) {
        var data
        try { data = JSON.parse(String(contents)) }
        catch (error) { busy = false; statusText = "Invalid backend response"; return }
        if (type === Protocol.stateResponse) {
            busy = false
            readingProgress = data.progress || { entries: {} }
            levelFilter = levelFilters.indexOf(readingProgress.level_filter) >= 0 ?
                readingProgress.level_filter : ""
            if (data.authenticated) {
                send(Protocol.top, {})
                sendBackground(Protocol.studied, {})
            }
            else statusText = "Login required — import your browser session and reinstall"
        } else if (type === Protocol.dataResponse) {
            if (data.kind === "lesson") { busy = false; showLesson(data.payload) }
            else if (data.kind === "studied") {
                var studied = {}
                for (var studiedIndex = 0; studiedIndex < data.payload.length; ++studiedIndex)
                    studied[String(data.payload[studiedIndex])] = true
                remoteStudied = studied
                if (listingPayload) refreshListing("No stories found")
            }
            else { busy = false; showListing(data.kind, data.payload) }
        } else if (type === Protocol.errorResponse) {
            busy = false
            statusText = data.message || "Request failed"
        } else if (type === Protocol.progressResponse) {
            if (data.studied_id) {
                var updatedStudied = {}
                for (var studiedID in remoteStudied) updatedStudied[studiedID] = remoteStudied[studiedID]
                updatedStudied[String(data.studied_id)] = true
                remoteStudied = updatedStudied
                readingProgress = data.progress || readingProgress
            } else readingProgress = data
            if (listingPayload) refreshListing("No stories found")
            statusText = ""
        }
    }

    function wordText(word) { return word.tc_hanzi || word.hanzi || "" }
    function isSelectableWord(word) {
        return /[A-Za-z0-9\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/.test(String(wordText(word)))
    }
    function measuredTokenWidth(word) {
        hanziMeasure.text = wordText(word)
        var width = hanziMeasure.implicitWidth
        if (showPinyin) {
            pinyinMeasure.text = word.pinyin || " "
            width = Math.max(width, pinyinMeasure.implicitWidth)
        }
        return width + 14
    }

    function isClosingPunctuation(word) {
        var text = String(wordText(word))
        return /^[。！？!?，,、；;：:…）》】”’]+$/.test(text)
    }

    function rebuildPagination(resumePosition) {
        var starts = [0]
        var availableWidth = Math.max(100, wordFlow.width)
        var availableHeight = Math.max(100, wordFlow.height)
        var rowHeight = showPinyin ? 84 : 65
        var lineWidth = 0
        var usedHeight = 0
        var pageHasWords = false
        for (var index = 0; index < words.length; ++index) {
            var word = words[index] || {}
            var hanzi = String(word.hanzi || word.tc_hanzi || "")
            if (hanzi.indexOf("\n") >= 0) {
                if (lineWidth > 0) {
                    usedHeight += rowHeight + wordFlow.spacing
                    lineWidth = 0
                }
                var firstSentenceEnd = sentenceEnds.length ? Number(sentenceEnds[0]) : -1
                var breakHeight = firstSentenceEnd >= 0 && index <= firstSentenceEnd + 1 ? 32 : 18
                if (pageHasWords && usedHeight + breakHeight > availableHeight) {
                    starts.push(index + 1)
                    usedHeight = 0
                    pageHasWords = false
                } else usedHeight += breakHeight + wordFlow.spacing
                continue
            }
            var tokenWidth = Math.min(availableWidth, measuredTokenWidth(word))
            if (lineWidth > 0 && lineWidth + wordFlow.spacing + tokenWidth > availableWidth) {
                usedHeight += rowHeight + wordFlow.spacing
                lineWidth = 0
            }
            if (pageHasWords && usedHeight + rowHeight > availableHeight) {
                if (isClosingPunctuation(word) && index > starts[starts.length - 1]) {
                    starts.push(index - 1)
                    usedHeight = 0
                    lineWidth = 0
                    pageHasWords = false
                    index -= 2
                    continue
                }
                starts.push(index)
                usedHeight = 0
                lineWidth = 0
                pageHasWords = false
            }
            lineWidth += (lineWidth > 0 ? wordFlow.spacing : 0) + tokenWidth
            pageHasWords = true
        }
        if (starts[starts.length - 1] !== words.length) starts.push(words.length)
        pageStarts = starts
        page = 0
        for (var pageIndex = 0; pageIndex < pageStarts.length - 1; ++pageIndex) {
            if (resumePosition >= pageStarts[pageIndex] && resumePosition < pageStarts[pageIndex + 1]) {
                page = pageIndex
                break
            }
        }
    }

    function currentPageStart() { return pageStarts[Math.min(page, pageStarts.length - 2)] || 0 }
    function currentPageEnd() { return pageStarts[Math.min(page + 1, pageStarts.length - 1)] || words.length }
    function isLastPage() { return page >= pageStarts.length - 2 }

    function turnPage(direction) {
        selectedWord = -1
        if (direction > 0 && !isLastPage()) page++
        else if (direction < 0 && page > 0) page--
        else if (direction < 0) return
        var finished = isLastPage()
        saveProgress(finished)
        if (finished) markRemoteRead()
    }

    function beginSwipe(x, y) {
        swipeStartX = x
        swipeStartY = y
        swipeHandled = false
    }

    function finishSwipe(x, y) {
        var dx = x - swipeStartX
        var dy = y - swipeStartY
        if (Math.abs(dx) < 100 || Math.abs(dx) < Math.abs(dy) * 1.5) return false
        swipeHandled = true
        turnPage(dx < 0 ? 1 : -1)
        return true
    }

    function pageItems() {
        var items = []
        var start = currentPageStart()
        var end = currentPageEnd()
        for (var index = start; index < end; ++index) {
            var word = words[index] || {}
            var hanzi = String(word.hanzi || word.tc_hanzi || "")
            if (hanzi.indexOf("\n") >= 0) {
                var firstSentenceEnd = sentenceEnds.length ? Number(sentenceEnds[0]) : -1
                items.push({
                    separator: true,
                    titleBreak: firstSentenceEnd >= 0 && index <= firstSentenceEnd + 1,
                    absoluteIndex: -1,
                    word: {}
                })
            } else {
                items.push({ separator: false, absoluteIndex: index, word: word })
            }
        }
        return items
    }

    function selectedTranslation() {
        if (selectedWord < 0) return ""
        for (var i = 0; i < sentenceEnds.length; ++i)
            if (selectedWord < Number(sentenceEnds[i])) return translations[i] || ""
        return ""
    }

    function toggleWord(index, item) {
        if (selectedWord === index) {
            selectedWord = -1
            return
        }
        selectedWord = index
        var position = item.mapToItem(root, 0, item.height)
        lookupX = Math.max(48, Math.min(root.width - 668, position.x + item.width / 2 - 310))
        lookupY = position.y + 10
        if (lookupY + 180 > readerNav.y - 12)
            lookupY = Math.max(translationArea.y + translationArea.height + 12,
                               position.y - item.height - 180)
    }

    AppLoad {
        id: endpoint
        applicationID: "duchinese-remarkable"
        onMessageReceived: (type, contents) => root.receive(type, contents)
    }

    Component.onCompleted: send(Protocol.bootstrap, {})

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
            visible: root.screen !== "reader"
            anchors.left: parent.left
            anchors.leftMargin: booksBackButton.visible ? 194 : 44
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 360
            text: root.heading
            elide: Text.ElideRight
            color: "black"
            font.family: "Noto Sans"
            font.pixelSize: 36
            font.bold: true
        }
        Column {
            visible: root.screen === "reader"
            anchors.left: parent.left; anchors.leftMargin: 44
            anchors.right: parent.right; anchors.rightMargin: 110
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Text {
                width: parent.width; text: root.heading
                elide: Text.ElideRight; color: "black"
                font.family: "Noto Sans"; font.pixelSize: 31; font.bold: true
            }
            Text {
                visible: root.readerChapterTitle !== ""
                width: parent.width; text: root.readerChapterTitle
                elide: Text.ElideRight; color: "#444"
                font.family: "Noto Sans"; font.pixelSize: 20
            }
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
            model: [
                { label: "Featured", type: Protocol.top },
                { label: "Latest", type: Protocol.latest }
            ]
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
            MouseArea {
                anchors.fill: parent
                onClicked: root.send(Protocol.search, { query: searchInput.text })
            }
        }
    }

    Rectangle {
        id: continueCard
        visible: root.screen === "library" && root.listingKind !== "course" &&
            root.readingProgress.last !== undefined && root.readingProgress.last !== null
        anchors.top: navigation.bottom; anchors.topMargin: 16
        anchors.left: parent.left; anchors.right: parent.right
        anchors.leftMargin: 32; anchors.rightMargin: 32
        height: 104; color: "black"
        Text {
            x: 22; y: 13; width: parent.width - 190
            text: "Continue reading"
            color: "white"; font.pixelSize: 18
        }
        Text {
            x: 22; y: 44; width: parent.width - 190
            text: root.readingProgress.last ? root.readingProgress.last.title : ""
            color: "white"; font.family: "Noto Sans"
            font.pixelSize: 27; font.bold: true; elide: Text.ElideRight
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            text: "Continue ›"; color: "white"; font.pixelSize: 22
        }
        MouseArea { anchors.fill: parent; onClicked: root.continueReading() }
    }

    ListView {
        visible: root.screen === "library"
        anchors.top: continueCard.visible ? continueCard.bottom : navigation.bottom
        anchors.topMargin: 18
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
                x: 22; y: 16; width: parent.width - (itemStarted ? 170 : 110)
                text: itemTitle
                elide: Text.ElideRight
                font.family: "Noto Sans"; font.pixelSize: 29; font.bold: true
            }
            Text {
                x: 22; y: 65; width: parent.width - 110
                text: itemLocked ? "Locked" :
                    (itemCourse ? "Course · " : "") + itemSubtitle
                elide: Text.ElideRight; font.pixelSize: 19; color: "#444"
            }
            Text {
                visible: !itemStarted
                anchors.right: parent.right; anchors.rightMargin: 26
                anchors.verticalCenter: parent.verticalCenter
                text: itemCourse ? "›" : "读"
                font.family: chineseFont.name; font.pixelSize: 36
            }
            Rectangle {
                visible: itemStarted
                anchors.right: parent.right; anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                width: 116; height: 48; radius: 3
                color: itemRead ? "black" : "white"
                border.width: itemRead ? 0 : 2; border.color: "black"
                Text {
                    anchors.centerIn: parent
                    text: itemRead ? "✓ Read" : "Reading"
                    color: itemRead ? "white" : "black"
                    font.pixelSize: 19; font.bold: true
                }
            }
            MouseArea {
                anchors.fill: parent
                enabled: !itemLocked
                onClicked: root.openItem(itemCourse, itemPath, itemRawTitle, itemLevel,
                                         itemID, itemChapterLabel)
            }
        }
    }

    Rectangle {
        id: translationArea
        visible: root.screen === "reader"
        anchors.top: toolbar.bottom; anchors.topMargin: 20
        anchors.left: parent.left; anchors.leftMargin: 48
        anchors.right: parent.right; anchors.rightMargin: 48
        height: 116
        color: "white"; border.width: 2; border.color: "black"
        Text {
            anchors.fill: parent; anchors.margins: 16
            text: !root.showSentenceTranslation ? "Tap to show sentence translation" :
                  root.selectedWord < 0 ? "Select a word to show its sentence translation" :
                  (root.selectedTranslation() || "No sentence translation available")
            wrapMode: Text.Wrap
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            font.family: "Noto Sans"; font.pixelSize: 23
            color: root.showSentenceTranslation ? "black" : "#555"
        }
        MouseArea {
            anchors.fill: parent
            onClicked: root.showSentenceTranslation = !root.showSentenceTranslation
        }
    }

    MouseArea {
        id: readerBackground
        visible: root.screen === "reader"
        anchors.top: translationArea.bottom; anchors.topMargin: 24
        anchors.left: parent.left; anchors.leftMargin: 48
        anchors.right: parent.right; anchors.rightMargin: 48
        height: root.height - 500
        onPressed: (mouse) => root.beginSwipe(mouse.x, mouse.y)
        onReleased: (mouse) => root.finishSwipe(mouse.x, mouse.y)
        onClicked: { if (!root.swipeHandled) root.selectedWord = -1 }
    }

    Flow {
        id: wordFlow
        visible: root.screen === "reader"
        anchors.top: translationArea.bottom; anchors.topMargin: 24
        anchors.left: parent.left; anchors.leftMargin: 48
        anchors.right: parent.right; anchors.rightMargin: 48
        height: root.height - 500
        spacing: 5

        Repeater {
            model: root.pageItems()
            Rectangle {
                property int absoluteIndex: modelData.absoluteIndex
                property bool separator: modelData.separator
                width: separator ? wordFlow.width : tokenColumn.width + 14
                height: separator ? (modelData.titleBreak ? 32 : 18) : (root.showPinyin ? 84 : 65)
                color: !separator && root.isSelectableWord(modelData.word) &&
                       root.selectedWord === absoluteIndex ? "#dddddd" : "white"
                border.width: !separator && root.isSelectableWord(modelData.word) &&
                              root.selectedWord === absoluteIndex ? 2 : 0
                Column {
                    id: tokenColumn
                    anchors.centerIn: parent
                    visible: !separator
                    Text { visible: root.showPinyin; anchors.horizontalCenter: parent.horizontalCenter; text: modelData.word.pinyin || " "; font.pixelSize: 17 }
                    Text { text: root.wordText(modelData.word); font.family: chineseFont.name; font.pixelSize: 42; color: "black" }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: !separator && root.isSelectableWord(modelData.word)
                    onPressed: (mouse) => root.beginSwipe(mouse.x, mouse.y)
                    onReleased: (mouse) => root.finishSwipe(mouse.x, mouse.y)
                    onClicked: { if (!root.swipeHandled) root.toggleWord(absoluteIndex, parent) }
                }
            }
        }
    }

    Rectangle {
        visible: root.screen === "reader" && root.selectedWord >= 0
        x: root.lookupX; y: root.lookupY
        width: 620; height: 180; z: 20
        color: "white"; border.width: 3; border.color: "black"
        Text {
            anchors.fill: parent; anchors.margins: 22
            text: root.selectedWord < 0 ? "" :
                root.wordText(root.words[root.selectedWord]) + "   " + (root.words[root.selectedWord].pinyin || "") + "\n" +
                (root.words[root.selectedWord].meaning || "")
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
                { label: (root.page + 1) + " / " + Math.max(1, root.pageStarts.length - 1), action: "none" },
                { label: root.isLastPage() ? "Finish ✓" : "Next ›", action: "next" }
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
                            else root.backFromReader()
                        } else if (modelData.action === "next") {
                            root.turnPage(1)
                        }
                        else if (modelData.action === "pinyin") {
                            var position = root.currentPageStart()
                            root.showPinyin = !root.showPinyin
                            Qt.callLater(function() { root.rebuildPagination(position) })
                        }
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

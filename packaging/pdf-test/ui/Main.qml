import QtQuick 2.15
import "BuildInfo.js" as BuildInfo
import net.asivery.ApploadUtils

Rectangle {
    id: root
    anchors.fill: parent
    color: "white"
    signal close
    function unloading() { reader.saveProgress() }
    Component.onCompleted: console.log("[PDF Reader Test] running build " + BuildInfo.id)
    DisplayMethodArea { anchors.fill: parent; displayMethod: DisplayMethodArea.Fast }
    PdfPage { id: reader; anchors.fill: parent; onClose: root.close() }
}

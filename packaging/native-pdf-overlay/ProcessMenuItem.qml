import QtQuick
import ark.controls as ArkControls
import "ProcessingClient.js" as ProcessingClient

ArkControls.FoldoutItem {
    id: control
    property string documentId: ""
    property var job: ({state: "idle"})
    property bool requesting: false
    property string serviceError: ""
    iconSource: "qrc:/ark/icons/hwc"
    label: job.state === "running" ? "Stop Chinese processing" :
           job.state === "cancelling" ? "Stopping Chinese processing…" :
           job.state === "complete" ? "Chinese lookup ready" :
           (job.state === "error" || job.state === "paused") ? "Resume Chinese processing" : "Process Chinese document"
    description: serviceError || (job.state === "running" ? job.message + " · " + job.done + "/" + job.total :
                 job.state === "cancelling" ? "Stopping current requests · " + job.done + "/" + job.total :
                 job.state === "complete" ? job.total + " pages processed" :
                 (job.state === "error" || job.state === "paused") ? job.message : "Whole PDF · cloud OCR and translations")
    enabled: documentId !== "" && !requesting && job.state !== "cancelling" && job.state !== "complete"

    function refresh() {
        var id = documentId
        ProcessingClient.request(id, "", "GET", function(value, status) {
            if (!control || id !== control.documentId) return
            if (value) { control.job = value; control.serviceError = "" }
            else control.serviceError = status === 404 ? "Download this PDF first" : "Processing service unavailable"
        })
    }
    onDocumentIdChanged: { job = ({state: "idle"}); serviceError = ""; if (documentId) refresh() }
    onVisibleChanged: { if (visible && documentId) refresh() }
    onClicked: {
        requesting = true
        var id = documentId
        var stopping = job.state === "running"
        ProcessingClient.request(id, stopping ? "/cancel" : "/process", "POST", function(value, status, message) {
            if (!control) return
            control.requesting = false
            if (id !== control.documentId) return
            if (value) { control.job = value; control.serviceError = "" }
            else { control.serviceError = status === 409 ? message.trim() : "Could not update processing"; control.refresh() }
        })
    }
    Timer { interval: 2500; repeat: true; running: control.visible && control.documentId !== ""; onTriggered: control.refresh() }
}

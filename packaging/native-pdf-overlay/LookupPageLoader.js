.pragma library

var cache = {}

function getPage(documentId, pageNumber, availablePages) {
    if (!availablePages || availablePages.indexOf(pageNumber) < 0) return null
    var key = documentId + "/" + pageNumber
    if (cache[key]) return cache[key]
    var url = "qrc:/duchinese-pdf-overlay/data/" + documentId
        + "/page-" + ("00" + pageNumber).slice(-3) + ".js"
    var result = Qt.include(url)
    if (result.status !== 0) {
        console.warn("[PDF lookup] Could not load page data " + key)
        return null
    }
    cache[key] = lookupData
    return cache[key]
}

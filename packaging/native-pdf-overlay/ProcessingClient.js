.pragma library

var baseUrl = "http://127.0.0.1:9876/v1/documents/"
function request(documentId, suffix, method, callback) {
    if (!/^[a-f0-9-]{36}$/.test(documentId)) return
    var xhr = new XMLHttpRequest()
    xhr.open(method, baseUrl + documentId + suffix)
    if (method === "POST") {
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.setRequestHeader("X-DuChinese-Local", "1")
    }
    xhr.onreadystatechange = function() {
        if (xhr.readyState !== XMLHttpRequest.DONE) return
        var value = null
        if (xhr.status >= 200 && xhr.status < 300) {
            try { value = JSON.parse(xhr.responseText) } catch (error) {}
        }
        callback(value, xhr.status, xhr.responseText)
    }
    xhr.send(method === "POST" ? "{}" : null)
}

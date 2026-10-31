// Scriptable loader: paste this once into a Scriptable script and use that script for all widgets.
// It runs progress-widget.js from the iCloud "Unitutor" folder, so later updates need no copy and paste.
const fm = FileManager.local()
const file = fm.joinPath(fm.bookmarkedPath("Unitutor"), "progress-widget.js")
await fm.downloadFileFromiCloud(file)
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
await new AsyncFunction(fm.readString(file))()

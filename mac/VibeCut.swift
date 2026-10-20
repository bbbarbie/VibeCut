// VibeCut.app's window.
//
// The app is the same local web app as on a developer's Mac: this launcher
// starts the bundled server (Resources/server/vibecut-server) on this Mac
// only, and shows its page in a native window. Clips never leave the Mac.
// Built by mac/build.sh; macOS 13+, Apple silicon.

import AppKit
import WebKit

let PORTS = 8770...8779   // a steady port keeps what the page saved in this window (sizes, profile)

final class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate, WKDownloadDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var server: Process?
    var port = PORTS.lowerBound
    var downloads: [ObjectIdentifier: URL] = [:]

    var home: URL { URL(string: "http://127.0.0.1:\(port)/")! }
    var logURL: URL {
        let d = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Logs/VibeCut")
        try? FileManager.default.createDirectory(at: d, withIntermediateDirectories: true)
        return d.appendingPathComponent("server.log")
    }

    func applicationDidFinishLaunching(_ note: Notification) {
        buildMenu()
        let config = WKWebViewConfiguration()
        config.preferences.isElementFullscreenEnabled = true
        config.mediaTypesRequiringUserActionForPlayback = []
        web = WKWebView(frame: .zero, configuration: config)
        web.uiDelegate = self
        web.navigationDelegate = self
        web.allowsMagnification = true

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 900),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "VibeCut"
        window.minSize = NSSize(width: 900, height: 600)
        window.contentView = web
        window.center()
        window.setFrameAutosaveName("VibeCut")
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        say("Opening VibeCut…")
        startServer()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ note: Notification) {
        let s = server
        server = nil
        s?.terminate()
    }

    // MARK: the server

    func freePort() -> Int? {
        for p in PORTS {
            let s = socket(AF_INET, SOCK_STREAM, 0)
            defer { close(s) }
            var addr = sockaddr_in()
            addr.sin_family = sa_family_t(AF_INET)
            addr.sin_port = in_port_t(UInt16(p).bigEndian)
            addr.sin_addr.s_addr = inet_addr("127.0.0.1")
            let ok = withUnsafePointer(to: &addr) {
                $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                    Darwin.bind(s, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
                }
            }
            if ok { return p }
        }
        return nil
    }

    func startServer() {
        let res = Bundle.main.resourceURL!
        guard let p = freePort() else {
            return say("VibeCut couldn't find a free port (8770–8779). Quit other copies of VibeCut and open it again.")
        }
        port = p
        var env = ProcessInfo.processInfo.environment
        env["VIBECUT_PORT"] = String(port)
        env["VIBECUT_HELPERS"] = res.appendingPathComponent("helpers").path
        // ffmpeg, ffprobe and yt-dlp come with the app; a Finder launch has almost no PATH
        env["PATH"] = res.appendingPathComponent("bin").path + ":" + (env["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")
        let proc = Process()
        proc.executableURL = res.appendingPathComponent("server/vibecut-server")
        proc.environment = env
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        if let log = try? FileHandle(forWritingTo: logURL) {
            proc.standardOutput = log
            proc.standardError = log
        }
        proc.terminationHandler = { [weak self] p in
            DispatchQueue.main.async { self?.serverStopped(p.terminationStatus) }
        }
        do {
            try proc.run()
        } catch {
            return say("VibeCut couldn't start: \(error.localizedDescription)")
        }
        server = proc
        waitForServer(tries: 0)
    }

    func waitForServer(tries: Int) {
        guard let s = server, s.isRunning else { return }
        var req = URLRequest(url: home.appendingPathComponent("api/projects"))
        req.timeoutInterval = 1
        URLSession.shared.dataTask(with: req) { [weak self] _, resp, _ in
            DispatchQueue.main.async {
                guard let self else { return }
                if (resp as? HTTPURLResponse)?.statusCode == 200 {
                    self.web.load(URLRequest(url: self.home))
                } else if tries < 240 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { self.waitForServer(tries: tries + 1) }
                } else {
                    self.say("VibeCut is taking too long to start. What happened is in \(self.logURL.path).")
                }
            }
        }.resume()
    }

    func serverStopped(_ status: Int32) {
        if NSApp.isRunning, server != nil {
            say("VibeCut stopped unexpectedly (\(status)). What happened is in \(logURL.path). Quit and open it again.")
        }
    }

    func say(_ text: String) {
        let safe = text.replacingOccurrences(of: "&", with: "&amp;").replacingOccurrences(of: "<", with: "&lt;")
        web.loadHTMLString("""
            <html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
            background:#faf8f5;color:#3a3530;font:20px Georgia,serif;text-align:center;padding:0 15%">
            <p>\(safe)</p></body></html>
            """, baseURL: nil)
    }

    // MARK: the window's page

    func isLocal(_ url: URL?) -> Bool {
        guard let url else { return true }
        return url.scheme == "about" || url.scheme == "blob" || url.scheme == "data"
            || (url.host == "127.0.0.1" && url.port == port)
    }

    // Links to the outside world (credits, a reference's page) open in the browser.
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if action.shouldPerformDownload { return decisionHandler(.download) }
        if action.targetFrame?.isMainFrame != false, !isLocal(action.request.url) {
            NSWorkspace.shared.open(action.request.url!)
            return decisionHandler(.cancel)
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
                 decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(response.canShowMIMEType ? .allow : .download)
    }

    // target="_blank" (the check's contact sheets): open in the browser.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }

    // Add clips / Add folder.
    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = !parameters.allowsDirectories
        panel.beginSheetModal(for: window) { r in completionHandler(r == .OK ? panel.urls : nil) }
    }

    // MARK: downloads (Download in the export dialog) land in ~/Downloads

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = self
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        let dir = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
        let name = suggestedFilename as NSString
        var url = dir.appendingPathComponent(suggestedFilename)
        var n = 2
        while FileManager.default.fileExists(atPath: url.path) {
            url = dir.appendingPathComponent("\(name.deletingPathExtension) \(n)")
                .appendingPathExtension(name.pathExtension)
            n += 1
        }
        downloads[ObjectIdentifier(download)] = url
        completionHandler(url)
    }

    func downloadDidFinish(_ download: WKDownload) {
        if let url = downloads.removeValue(forKey: ObjectIdentifier(download)) {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        downloads.removeValue(forKey: ObjectIdentifier(download))
    }

    // MARK: menus

    @objc func reload() { web.load(URLRequest(url: home)) }
    @objc func openInBrowser() { NSWorkspace.shared.open(web.url.flatMap { isLocal($0) && $0.scheme == "http" ? $0 : nil } ?? home) }
    @objc func showLog() { NSWorkspace.shared.activateFileViewerSelecting([logURL]) }

    func buildMenu() {
        let main = NSMenu()
        func add(_ title: String, _ items: [NSMenuItem]) {
            let item = NSMenuItem()
            let menu = NSMenu(title: title)
            for i in items { menu.addItem(i) }
            item.submenu = menu
            main.addItem(item)
        }
        func item(_ t: String, _ a: Selector, _ k: String, _ mods: NSEvent.ModifierFlags = .command) -> NSMenuItem {
            let i = NSMenuItem(title: t, action: a, keyEquivalent: k)
            i.keyEquivalentModifierMask = mods
            return i
        }
        add("VibeCut", [
            item("About VibeCut", #selector(NSApplication.orderFrontStandardAboutPanel(_:)), ""),
            .separator(),
            item("Hide VibeCut", #selector(NSApplication.hide(_:)), "h"),
            item("Hide Others", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option]),
            item("Show All", #selector(NSApplication.unhideAllApplications(_:)), ""),
            .separator(),
            item("Quit VibeCut", #selector(NSApplication.terminate(_:)), "q"),
        ])
        // No Undo / Redo here: Cmd-Z belongs to the page's own undo.
        add("Edit", [
            item("Cut", #selector(NSText.cut(_:)), "x"),
            item("Copy", #selector(NSText.copy(_:)), "c"),
            item("Paste", #selector(NSText.paste(_:)), "v"),
            item("Select All", #selector(NSText.selectAll(_:)), "a"),
        ])
        add("View", [
            item("Reload", #selector(reload), "r"),
            item("Open in Browser", #selector(openInBrowser), "o", [.command, .shift]),
            .separator(),
            item("Enter Full Screen", #selector(NSWindow.toggleFullScreen(_:)), "f", [.command, .control]),
        ])
        add("Window", [
            item("Minimize", #selector(NSWindow.performMiniaturize(_:)), "m"),
            item("Zoom", #selector(NSWindow.performZoom(_:)), ""),
        ])
        add("Help", [item("Show the Log", #selector(showLog), "")])
        NSApp.mainMenu = main
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()

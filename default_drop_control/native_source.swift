import AppKit
import Foundation

func die(_ message: String) -> Never {
  fputs("ERROR \(message)\n", stderr)
  exit(2)
}

func writeJSON(_ object: [String: Any], to path: String) {
  do {
    let data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
    try data.write(to: URL(fileURLWithPath: path), options: .atomic)
  } catch {
    fputs("WRITE_JSON_ERROR \(error)\n", stderr)
  }
}

let args = CommandLine.arguments
if args.count != 6 {
  die("usage: native-source <uri|file> <payload> <ready-json> <result-json> <label>")
}
let mode = args[1]
let payload = args[2]
let readyPath = args[3]
let resultPath = args[4]
let label = args[5]
let payloadURL: URL
if mode == "uri" {
  guard let parsed = URL(string: payload), let scheme = parsed.scheme, !scheme.isEmpty else {
    die("invalid URI: \(payload)")
  }
  payloadURL = parsed
} else if mode == "file" {
  payloadURL = URL(fileURLWithPath: payload)
} else {
  die("unknown mode \(mode)")
}

final class DragView: NSView, NSDraggingSource {
  let payloadURL: URL
  let mode: String
  let resultPath: String
  let label: String

  init(frame: NSRect, payloadURL: URL, mode: String, resultPath: String, label: String) {
    self.payloadURL = payloadURL
    self.mode = mode
    self.resultPath = resultPath
    self.label = label
    super.init(frame: frame)
    wantsLayer = true
    layer?.backgroundColor = NSColor(calibratedRed: 0.25, green: 0.12, blue: 0.65, alpha: 1).cgColor
  }
  required init?(coder: NSCoder) { fatalError("init(coder:) has not been implemented") }

  override func draw(_ dirtyRect: NSRect) {
    super.draw(dirtyRect)
    let title = "NATIVE \(mode.uppercased()) DRAG SOURCE\n\(label)\n\(payloadURL.absoluteString)"
    let paragraph = NSMutableParagraphStyle()
    paragraph.alignment = .center
    let attrs: [NSAttributedString.Key: Any] = [
      .font: NSFont.boldSystemFont(ofSize: 18),
      .foregroundColor: NSColor.white,
      .paragraphStyle: paragraph
    ]
    title.draw(in: bounds.insetBy(dx: 24, dy: 180), withAttributes: attrs)
  }

  override func mouseDown(with event: NSEvent) {
    print("SOURCE_MOUSE_DOWN \(event.locationInWindow)", terminator: "\n")
    let writer = payloadURL as NSURL
    let item = NSDraggingItem(pasteboardWriter: writer)
    let image = NSImage(size: NSSize(width: 160, height: 84))
    image.lockFocus()
    NSColor.systemPurple.setFill()
    NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: 160, height: 84), xRadius: 14, yRadius: 14).fill()
    let text = mode == "file" ? "LOCAL HTML FILE" : "HTTP URL"
    text.draw(at: NSPoint(x: 14, y: 32), withAttributes: [
      .font: NSFont.boldSystemFont(ofSize: 15),
      .foregroundColor: NSColor.white
    ])
    image.unlockFocus()
    let local = convert(event.locationInWindow, from: nil)
    item.setDraggingFrame(NSRect(x: local.x - 80, y: local.y - 42, width: 160, height: 84), contents: image)
    let session = beginDraggingSession(with: [item], event: event, source: self)
    session.animatesToStartingPositionsOnCancelOrFail = false
    writeJSON([
      "event": "drag-session-started",
      "mode": mode,
      "payload": payloadURL.absoluteString,
      "time": Date().timeIntervalSince1970
    ], to: resultPath)
  }

  func draggingSession(_ session: NSDraggingSession, sourceOperationMaskFor context: NSDraggingContext) -> NSDragOperation {
    return .copy
  }

  func ignoreModifierKeys(for session: NSDraggingSession) -> Bool { true }

  func draggingSession(_ session: NSDraggingSession, endedAt screenPoint: NSPoint, operation: NSDragOperation) {
    print("SOURCE_DRAG_ENDED point=\(screenPoint) operation=\(operation.rawValue)", terminator: "\n")
    writeJSON([
      "event": "drag-session-ended",
      "mode": mode,
      "payload": payloadURL.absoluteString,
      "screenPoint": [screenPoint.x, screenPoint.y],
      "operationRaw": operation.rawValue,
      "time": Date().timeIntervalSince1970
    ], to: resultPath)
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { NSApp.terminate(nil) }
  }
}

final class Delegate: NSObject, NSApplicationDelegate {
  var window: NSWindow?
  func applicationDidFinishLaunching(_ notification: Notification) {
    let screenFrame = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    let frame = NSRect(x: 0, y: screenFrame.maxY - 30 - 680, width: 400, height: 680)
    let w = NSWindow(contentRect: frame, styleMask: [.titled, .closable, .miniaturizable], backing: .buffered, defer: false)
    w.title = "Default-drop native source"
    w.isReleasedWhenClosed = false
    w.contentView = DragView(frame: w.contentLayoutRect, payloadURL: payloadURL, mode: mode, resultPath: resultPath, label: label)
    w.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    window = w
    writeJSON([
      "event": "source-ready",
      "mode": mode,
      "payload": payloadURL.absoluteString,
      "windowFrame": [w.frame.origin.x, w.frame.origin.y, w.frame.size.width, w.frame.size.height],
      "screenFrame": [screenFrame.origin.x, screenFrame.origin.y, screenFrame.size.width, screenFrame.size.height],
      "time": Date().timeIntervalSince1970
    ], to: readyPath)
    print("SOURCE_READY mode=\(mode) payload=\(payloadURL.absoluteString) frame=\(w.frame)", terminator: "\n")
  }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = Delegate()
app.delegate = delegate
app.run()

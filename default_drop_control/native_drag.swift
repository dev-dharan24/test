import AppKit
import CoreGraphics
import Foundation

func fail(_ message: String) -> Never { fputs("ERROR \(message)\n", stderr); exit(2) }
let args = CommandLine.arguments
if args.count != 6 { fail("usage: native-drag startX startY endX endY pasteboardLog") }
guard let sx = Double(args[1]), let sy = Double(args[2]), let ex = Double(args[3]), let ey = Double(args[4]) else { fail("bad coordinates") }
let outputURL = URL(fileURLWithPath: args[5])

func post(_ type: CGEventType, _ point: CGPoint) {
  guard let event = CGEvent(mouseEventSource: nil, mouseType: type, mouseCursorPosition: point, mouseButton: .left) else { fail("CGEvent") }
  event.setIntegerValueField(.mouseEventClickState, value: 1)
  event.post(tap: .cghidEventTap)
}

func snapshot(_ label: String) -> [String: Any] {
  let pb = NSPasteboard(name: .drag)
  let types = (pb.types ?? []).map { $0.rawValue }
  let values: [String: String] = [
    "public.url": pb.string(forType: .URL) ?? "",
    "public.file-url": pb.string(forType: .fileURL) ?? "",
    "public.utf8-plain-text": pb.string(forType: .string) ?? "",
    "public.html": pb.string(forType: .html) ?? "",
    "public.url-name": pb.string(forType: NSPasteboard.PasteboardType("public.url-name")) ?? ""
  ]
  let filenames = pb.propertyList(forType: NSPasteboard.PasteboardType("NSFilenamesPboardType")) ?? NSNull()
  print("PASTEBOARD \(label) types=\(types) values=\(values) filenames=\(filenames)", terminator: "\n")
  return ["label": label, "types": types, "values": values, "filenames": filenames, "changeCount": pb.changeCount]
}

let start = CGPoint(x: sx, y: sy)
let end = CGPoint(x: ex, y: ey)
CGWarpMouseCursorPosition(start)
usleep(350_000)
post(.mouseMoved, start)
usleep(250_000)
post(.leftMouseDown, start)
usleep(300_000)
var shots: [[String: Any]] = []
for i in 1...80 {
  let t = Double(i) / 80.0
  let point = CGPoint(x: sx + (ex - sx) * t, y: sy + (ey - sy) * t)
  post(.leftMouseDragged, point)
  if i == 14 { usleep(350_000); shots.append(snapshot("after-threshold")) }
  usleep(12_000)
}
shots.append(snapshot("before-drop"))
usleep(250_000)
post(.leftMouseUp, end)
usleep(750_000)
shots.append(snapshot("after-drop"))
let object: [String: Any] = ["start": [sx, sy], "end": [ex, ey], "shots": shots]
let data = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
try data.write(to: outputURL, options: .atomic)
print("NATIVE_DRAG_DONE", terminator: "\n")

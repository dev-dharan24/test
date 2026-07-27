import AppKit
import CoreGraphics
import Foundation

func fail(_ s: String) -> Never { fputs("ERROR \(s)\n", stderr); exit(2) }
let a=CommandLine.arguments
if a.count != 6 { fail("usage: drag startX startY endX endY pasteboardLog") }
guard let sx=Double(a[1]), let sy=Double(a[2]), let ex=Double(a[3]), let ey=Double(a[4]) else { fail("bad coords") }
let logURL=URL(fileURLWithPath:a[5])
func event(_ type: CGEventType, _ p: CGPoint) {
  guard let e=CGEvent(mouseEventSource:nil, mouseType:type, mouseCursorPosition:p, mouseButton:.left) else { fail("CGEvent") }
  e.setIntegerValueField(.mouseEventClickState, value:1)
  e.post(tap:.cghidEventTap)
}
func snapshot(_ label:String) -> [String:Any] {
  let pb=NSPasteboard(name:.drag)
  let types=(pb.types ?? []).map{$0.rawValue}
  let html=pb.string(forType:.html) ?? ""
  let plain=pb.string(forType:.string) ?? ""
  print("PASTEBOARD \(label) types=\(types) htmlBytes=\(html.utf8.count) plainBytes=\(plain.utf8.count)")
  return ["label":label,"types":types,"html":html,"plain":plain,"changeCount":pb.changeCount]
}
let start=CGPoint(x:sx,y:sy), end=CGPoint(x:ex,y:ey)
CGWarpMouseCursorPosition(start); usleep(300_000)
event(.mouseMoved,start); usleep(200_000)
event(.leftMouseDown,start); usleep(250_000)
var shots:[[String:Any]]=[]
for i in 1...80 {
  let t=Double(i)/80.0
  let p=CGPoint(x:sx+(ex-sx)*t, y:sy+(ey-sy)*t)
  event(.leftMouseDragged,p)
  if i == 12 { usleep(350_000); shots.append(snapshot("after-threshold")) }
  usleep(12_000)
}
shots.append(snapshot("before-drop")); usleep(200_000)
event(.leftMouseUp,end); usleep(600_000)
shots.append(snapshot("after-drop"))
let obj:[String:Any] = ["start":[sx,sy],"end":[ex,ey],"shots":shots]
let data=try JSONSerialization.data(withJSONObject:obj,options:[.prettyPrinted,.sortedKeys])
try data.write(to:logURL)
print("DRAG_DONE \(String(data:data,encoding:.utf8)!)")

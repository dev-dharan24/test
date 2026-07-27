import AppKit
import CoreGraphics
import Foundation

func fail(_ s:String) -> Never { fputs("ERROR \(s)\n",stderr); exit(2) }
let a=CommandLine.arguments
if a.count != 6 { fail("usage: paste sourceX sourceY targetX targetY pasteboardLog") }
guard let sx=Double(a[1]),let sy=Double(a[2]),let tx=Double(a[3]),let ty=Double(a[4]) else { fail("bad coords") }
let logURL=URL(fileURLWithPath:a[5])
func mouse(_ type:CGEventType,_ p:CGPoint) {
  guard let e=CGEvent(mouseEventSource:nil,mouseType:type,mouseCursorPosition:p,mouseButton:.left) else { fail("mouse event") }
  e.post(tap:.cghidEventTap)
}
func key(_ code:CGKeyCode,_ down:Bool) {
  guard let e=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down) else { fail("key event") }
  e.flags = .maskCommand; e.post(tap:.cghidEventTap)
}
func click(_ p:CGPoint) { mouse(.mouseMoved,p); usleep(150_000); mouse(.leftMouseDown,p); usleep(80_000); mouse(.leftMouseUp,p); usleep(250_000) }
func command(_ code:CGKeyCode) { key(code,true); usleep(100_000); key(code,false); usleep(500_000) }
func snapshot(_ label:String)->[String:Any] {
  let pb=NSPasteboard.general
  let types=(pb.types ?? []).map{$0.rawValue}
  let html=pb.string(forType:.html) ?? ""
  let plain=pb.string(forType:.string) ?? ""
  print("CLIPBOARD \(label) types=\(types) htmlBytes=\(html.utf8.count) plainBytes=\(plain.utf8.count)")
  return ["label":label,"types":types,"html":html,"plain":plain,"changeCount":pb.changeCount]
}
let source=CGPoint(x:sx,y:sy),target=CGPoint(x:tx,y:ty)
click(source)
command(8) // ANSI C
let copied=snapshot("after-command-c")
click(target)
command(9) // ANSI V
usleep(1_000_000)
let after=snapshot("after-command-v")
let obj:[String:Any]=["source":[sx,sy],"target":[tx,ty],"shots":[copied,after]]
let data=try JSONSerialization.data(withJSONObject:obj,options:[.prettyPrinted,.sortedKeys]); try data.write(to:logURL)
print("PASTE_DONE \(String(data:data,encoding:.utf8)!)")

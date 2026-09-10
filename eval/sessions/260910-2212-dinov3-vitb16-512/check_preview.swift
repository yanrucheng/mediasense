import AppKit
import WebKit

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let page = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
class Checker: NSObject, WKNavigationDelegate {
    var view: WKWebView!
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let js = """
        (async()=>{
          const groups=[...document.querySelectorAll('details.group')];
          document.querySelector('#expand').click();
          const expanded=groups.every(x=>x.open);
          document.querySelector('#collapse').click();
          const collapsed=groups.every(x=>!x.open);
          groups[0].open=true;
          const frames=document.querySelector('details.frames'); if(frames) frames.open=true;
          const imgs=[...document.images].slice(0,16);
          imgs.forEach(x=>x.loading='eager');
          await Promise.all(imgs.map(x=>x.decode().catch(()=>null)));
          return JSON.stringify({groups:groups.length,source_cards:document.querySelectorAll('[data-source]').length,expanded,collapsed,video_expanded:!!frames&&frames.open,decoded_images:imgs.filter(x=>x.naturalWidth>0).length,checked_images:imgs.length,title:document.title});
        })()
        """
        webView.callAsyncJavaScript("return await " + js, arguments: [:], in: nil, in: .page) { result in
            switch result {
            case .success(let value):
                print(value)
                let conf=WKSnapshotConfiguration()
                webView.takeSnapshot(with: conf) { image,error in
                    if let image=image, let tiff=image.tiffRepresentation, let bitmap=NSBitmapImageRep(data:tiff), let png=bitmap.representation(using:.png,properties:[:]) {
                        try? png.write(to:output)
                        exit(0)
                    }
                    print("snapshot error",error as Any); exit(2)
                }
            case .failure(let error): print(error);exit(1)
            }
        }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {print(error);exit(1)}
}
let check=Checker()
let configuration=WKWebViewConfiguration()
configuration.websiteDataStore = .nonPersistent()
check.view=WKWebView(frame:NSRect(x:0,y:0,width:1440,height:1100),configuration:configuration)
let window=NSWindow(contentRect:NSRect(x:0,y:0,width:1440,height:1100),styleMask:[.borderless],backing:.buffered,defer:false)
window.contentView=check.view
check.view.navigationDelegate=check
check.view.loadFileURL(page,allowingReadAccessTo:page.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent())
DispatchQueue.main.asyncAfter(deadline:.now()+45) {print("timeout");exit(3)}
app.run()

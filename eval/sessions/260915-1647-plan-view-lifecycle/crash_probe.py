"""Actual owned-browser crash; injected short idle policy, no Plan mutation."""

import json
from pathlib import Path
import subprocess
import sys
import time

from mediasense.runtime import plan_views
from mediasense.runtime._view_files import process_state

base = Path(sys.argv[1]).resolve()
config = json.loads((base / "installed-1/config.json").read_text())
state = json.loads((base / "installed-1/browser-report.json").read_text())
output = base / "browser-crash"
output.mkdir()
root = output / plan_views.build_identity()
root.mkdir()
code = """
from mediasense.runtime import _view_server as server
from mediasense.runtime._view_lifecycle import Lifecycle, Policy
original=server.ViewServer
server.ViewServer=lambda build,root: original(build,root=root,lifecycle=Lifecycle(policy=Policy(cache_idle=.3,service_idle=5,sweep_interval=.1)))
server.main()
"""
child = subprocess.Popen([sys.executable, "-c", code, str(root), root.name])
try:
    info = None
    deadline = time.monotonic() + 15
    while info is None and time.monotonic() < deadline:
        info = plan_views._info(root)
        time.sleep(0.02)
    assert info
    view = plan_views.rpc(
        info,
        "bind",
        {
            "workspace": config["workspace"],
            "dataset_ref": config["dataset_ref"],
            "work_ref": state["work_ref"],
            "revision": state["revision"],
        },
    )
    assert view["status"] == "ready"
    browser_script = r"""
const {chromium}=require(process.argv[1]);
(async()=>{
 const owner=await chromium.launchServer({executablePath:process.argv[2],headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
 const browser=await chromium.connect(owner.wsEndpoint());
 const page=await browser.newPage();await page.goto(process.argv[3]);await page.locator("summary").waitFor();
 const exited=new Promise(resolve=>browser.once("disconnected",resolve));
 const pid=owner.process().pid;owner.process().kill("SIGKILL");await exited;
 console.log(JSON.stringify({browser_pid:pid,browser_crashed:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    browser = json.loads(
        subprocess.check_output(
            [
                "node",
                "-e",
                browser_script,
                config["playwright"],
                config["browser"],
                view["revision_uri"],
            ],
            text=True,
            timeout=30,
        )
    )
    started = time.monotonic()
    assert child.wait(timeout=10) == 0
    ownership, header = process_state(root)
    assert ownership == "released" and header["exit_reason"] == "idle_timeout"
    result = {
        **browser,
        "service_pid": child.pid,
        "service_exited": True,
        "exit_reason": header["exit_reason"],
        "seconds_after_browser_crash": time.monotonic() - started,
        "policy": {"cache_idle": 0.3, "service_idle": 5},
        "unload_required": False,
    }
    (output / "report.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
finally:
    if child.poll() is None:
        child.terminate()
        child.wait(timeout=3)

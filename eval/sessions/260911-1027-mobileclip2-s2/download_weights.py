"""Resume bounded public weight downloads and verify the official SHA-256."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import subprocess

root = Path("/private/tmp/mediasense-mobileclip2-260911")
root.mkdir(parents=True, exist_ok=True)
(root / "checkpoint").mkdir(exist_ok=True)
p = root / "checkpoint/mobileclip2_s2.pt"
expected = "37c2d839a856491f2fcc82c40dc28672dbd0907235b4cd4c38dfff6457f0c09f"
if p.exists():
    if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
        raise ValueError("Existing checkpoint differs; use a new output path")
    print("Existing official checkpoint verified; no download")
    raise SystemExit(0)
parts = root / "parts"
parts.mkdir(exist_ok=True)
size = 398071149
chunk = 8 * 1024 * 1024
url = "https://modelscope.cn/api/v1/models/apple/MobileCLIP2-S2/repo?Revision=9b428c3d5b0eb80a1e83caf271d03314657c4f0f&FilePath=mobileclip2_s2.pt"


def fetch(i):
    a = i * chunk
    b = min(size, a + chunk) - 1
    p = parts / str(i)
    h = parts / (str(i) + ".headers")
    if p.exists() and p.stat().st_size == b - a + 1:
        return i
    subprocess.run(
        [
            "curl",
            "-sSL",
            "--fail",
            "--retry",
            "1",
            "--connect-timeout",
            "8",
            "--max-time",
            "45",
            "--range",
            f"{a}-{b}",
            url,
            "-D",
            str(h),
            "-o",
            str(p),
        ],
        check=True,
        timeout=110,
    )
    if p.stat().st_size != b - a + 1 or f"bytes {a}-{b}/{size}" not in h.read_text():
        raise ValueError("incorrect range")
    return i


n = (size + chunk - 1) // chunk
with ThreadPoolExecutor(max_workers=4) as pool:
    for k, f in enumerate(as_completed([pool.submit(fetch, i) for i in range(n)]), 1):
        f.result()
        print(f"downloaded {k}/{n} verified ranges", flush=True)
with p.open("xb") as out:
    for i in range(n):
        out.write((parts / str(i)).read_bytes())
h = hashlib.sha256(p.read_bytes()).hexdigest()
assert h == expected, h
print("verified official SHA256", h, flush=True)

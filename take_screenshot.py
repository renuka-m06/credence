import subprocess
import time
import sys
from pathlib import Path
import urllib.request

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
out_png = Path(r"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence\report_screen.png")
brain_dir = Path(r"C:\Users\PoornaTeja Shree\.gemini\antigravity\brain\7dc92f76-135e-439d-89cd-d3deb0c52543")

print(f"Edge exists: {Path(edge_path).exists()}")

# Start uvicorn server as subprocess
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "credence.server:app", "--host", "127.0.0.1", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=r"c:\Users\PoornaTeja Shree\OneDrive\Desktop\credence"
)

try:
    # Wait for server to be up
    started = False
    for i in range(25):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as resp:
                if resp.status == 200:
                    started = True
                    print("Server is healthy on port 8000!")
                    break
        except Exception:
            time.sleep(0.4)

    if not started:
        print("Server failed to start in time.")
        server.kill()
        out, err = server.communicate(timeout=2)
        print("Stdout:", out.decode(errors="ignore"))
        print("Stderr:", err.decode(errors="ignore"))
        sys.exit(1)

    # Now run Edge to take screenshot
    cmd = [
        edge_path,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--user-data-dir=" + str(Path.home() / "AppData" / "Local" / "Temp" / "edge_credence_temp"),
        "--window-size=1400,1350",
        f"--screenshot={str(out_png)}",
        "http://127.0.0.1:8000"
    ]
    print("Running Edge:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    print("Edge returncode:", res.returncode)
    print("Edge stdout:", res.stdout[:500] if res.stdout else "")
    print("Edge stderr:", res.stderr[:500] if res.stderr else "")

    if out_png.exists():
        print(f"Screenshot successfully created at: {out_png} (size: {out_png.stat().st_size} bytes)")
        # Also copy to brain directory so artifacts/markdown can display it
        brain_png = brain_dir / "report_screen.png"
        import shutil
        shutil.copy2(out_png, brain_png)
        print(f"Copied to brain dir: {brain_png}")
    else:
        print("Screenshot file was NOT created.")

finally:
    server.terminate()
    try:
        server.wait(timeout=3)
    except Exception:
        server.kill()
    print("Server stopped.")

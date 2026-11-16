"""Filme la page du reel image par image (Chrome sans interface) et encode avec ffmpeg.

Un fichier encodé par scène, mêmes réglages partout, puis assemblage sans réencodage.
"""
import asyncio
import base64
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

W, H, FPS = 1080, 1920, 30
ENC = [
    "-vf", "scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709,format=yuv420p",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), "-g", str(FPS * 2),
    "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
]


async def _open(browser, url):
    page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    logs = []
    page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"[erreur page] {e}"))
    await page.goto(url)
    try:
        await page.wait_for_function("window.__ready === true", timeout=20000)
    except Exception:
        raise RuntimeError("La page du reel ne s'est pas initialisée :\n" + "\n".join(logs))
    for line in logs:
        if "warn" in line or "erreur" in line or "error" in line:
            print("   page:", line)
    return page


async def _launch(p):
    return await p.chromium.launch(headless=True,
                                   args=["--allow-file-access-from-files", "--font-render-hinting=none", "--hide-scrollbars"])


async def _stills(url, times, outdir):
    async with async_playwright() as p:
        browser = await _launch(p)
        page = await _open(browser, url)
        paths = []
        for t in times:
            await page.evaluate("t => { window.__seek(t); }", t)
            path = Path(outdir) / f"still_{t:06.2f}.jpg"
            await page.screenshot(path=str(path), type="jpeg", quality=88)
            paths.append(path)
        await browser.close()
        return paths


async def _chunk(browser, url, f0, f1, out):
    page = await _open(browser, url)
    cdp = await page.context.new_cdp_session(page)
    tmp = out.with_name(out.stem + ".part.mp4")
    ff = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
         *ENC, str(tmp)], stdin=subprocess.PIPE)
    try:
        for f in range(f0, f1):
            await page.evaluate("t => { window.__seek(t); }", f / FPS)
            shot = await cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": 92, "optimizeForSpeed": True})
            ff.stdin.write(base64.b64decode(shot["data"]))
    finally:
        ff.stdin.close()
        rc = ff.wait()
        await page.close()
    if rc != 0:
        raise RuntimeError(f"ffmpeg a échoué sur {out.name}")
    tmp.rename(out)
    return out


async def _film(url, bounds, outdir, workers=2):
    outdir = Path(outdir)
    jobs = [(bounds[i], bounds[i + 1], outdir / f"scene_{i:02d}.mp4") for i in range(len(bounds) - 1)]
    queue = asyncio.Queue()
    for j in jobs:
        queue.put_nowait(j)

    async with async_playwright() as p:
        browser = await _launch(p)

        async def worker():
            while not queue.empty():
                f0, f1, out = queue.get_nowait()
                await _chunk(browser, url, f0, f1, out)
                print(f"   scène filmée : {out.name} ({f1 - f0} images)")

        await asyncio.gather(*[worker() for _ in range(workers)])
        await browser.close()
    return [j[2] for j in jobs]


def stills(url, times, outdir):
    return asyncio.run(_stills(url, times, outdir))


def film(url, total, cuts, outdir):
    n = int(round(total * FPS))
    bounds = [0] + [int(round(c * FPS)) for c in cuts] + [n]
    return asyncio.run(_film(url, bounds, outdir))


def assemble(scene_files, audio_wav, out_mp4):
    out_mp4 = Path(out_mp4)
    lst = out_mp4.with_name("scenes.txt")
    lst.write_text("".join(f"file '{Path(f).resolve()}'\n" for f in scene_files))
    silent = out_mp4.with_name("silent.part.mp4")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)], check=True)
    tmp = out_mp4.with_name(out_mp4.stem + ".part.mp4")
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", str(silent), "-i", str(audio_wav), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-movflags", "+faststart", str(tmp)], check=True)
    tmp.rename(out_mp4)
    silent.unlink(missing_ok=True)
    return out_mp4

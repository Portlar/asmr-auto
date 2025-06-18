#!/usr/bin/env python3
import os, subprocess, json, tempfile, random, time, sys, textwrap, shutil
from pathlib import Path
import openai, requests

openai.api_key = os.getenv("OPENAI_API_KEY")
COOKIE_TEXT   = os.getenv("YOUTUBE_COOKIES")         # may be None

SEARCH_QUERIES = [
    "asmr tapping",
    "asmr rain sounds",
    "asmr brushing microphone",
    "asmr keyboard",
    "asmr paper sounds",
    "asmr spray",
]

# ── Pixabay fallback (CC-0) ──────────────────────────────────────────────────
PIXABAY_IDS = [
    "48993",  # Calm‐rain
    "16606",  # Typing
    "17660",  # Wood tapping
]
PIXABAY_KEY = "pixabay"  # no key needed for direct download links

def pixabay_download(tmpdir: Path) -> tuple[Path,str,str]:
    """
    Try downloading one of the known Pixabay CC-0 videos.
    If all fail, generate a 10s blank test clip via ffmpeg.
    Returns (file_path, title, source_url).
    """
    import requests

    for vid_id in PIXABAY_IDS:
        url = f"https://cdn.pixabay.com/videvo_download/medium/{vid_id}.mp4"
        dst = tmpdir / "src.mp4"
        try:
            print(f"[INFO] Trying Pixabay clip {vid_id} → {url}")
            r = requests.get(url, timeout=30, stream=True)
            r.raise_for_status()
            with open(dst, "wb") as fp:
                for chunk in r.iter_content(chunk_size=1<<16):
                    fp.write(chunk)
            return dst, f"Pixabay clip {vid_id}", url
        except Exception as e:
            print(f"[WARN] Pixabay download failed for {vid_id}: {e}")

    # All Pixabay attempts failed → generate blank test video
    print("[INFO] All Pixabay downloads failed, generating blank clip with FFmpeg")
    dst = tmpdir / "src.mp4"
    # 10 seconds, 1080x1920, color test pattern + silent audio
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=1080x1920:duration=10:rate=30",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest", str(dst)
    ], check=True)
    return dst, "Generated test clip", "generated://test"

# ── YouTube search helpers ───────────────────────────────────────────────────
def yt_search(query: str, n: int = 20):
    cmd = [
        "yt-dlp",
        f"ytsearch{n}:{query} creative commons",
        "--print-json",
        "--skip-download",
        "--no-playlist",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return [json.loads(l) for l in out.strip().splitlines()]
    except subprocess.CalledProcessError:
        print(f"[WARN] yt-dlp search failed for {query!r}")
        return []

def pick_video():
    for _ in range(6):
        vids = yt_search(random.choice(SEARCH_QUERIES))
        if vids:
            return random.choice(vids)
    return None  # give up

def safe_download_youtube(url: str) -> Path | None:
    tmpdir = Path(tempfile.mkdtemp())
    dst    = tmpdir / "src.mp4"
    cmd = [
        "yt-dlp",
        "-f", "bv*+ba/best",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "--no-playlist",
        "--throttled-rate", "500K",
        "-o", str(dst),
        url,
    ]
    if COOKIE_TEXT:
        cfile = tmpdir / "cookies.txt"
        cfile.write_text(COOKIE_TEXT, encoding="utf-8")
        cmd[0:0] = ["yt-dlp"]  # just to align indices
        cmd.extend(["--cookies", str(cfile)])

    for attempt in range(3):
        try:
            subprocess.run(cmd, check=True)
            return dst
        except subprocess.CalledProcessError:
            print(f"[WARN] yt-dlp blocked (attempt {attempt+1})")
            time.sleep(2)
    return None

# ── FFmpeg crop ──────────────────────────────────────────────────────────────
def vertical_crop(src: Path) -> Path:
    dst = src.with_name("final.mp4")
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-ss", "0", "-t", "67",
            "-vf", "crop=in_h*9/16:in_h,scale=1080:1920",
            "-af", "loudnorm",
            "-y", str(dst),
        ],
        check=True,
    )
    return dst

# ── GPT title/description ────────────────────────────────────────────────────
def gen_meta(orig_title: str, src_url: str) -> Path:
    """
    Try GPT-4o for PT-BR metadata; on rate‐limit or error, use a basic fallback.
    """
    import openai, json, tempfile
    from pathlib import Path
    prompt = (
        "Crie JSON com 'titulo' (≤50 chars) e 'descricao' (≤120 chars) "
        f"em PT-BR para vídeo ASMR cujo gatilho é: {orig_title!r}"
    )
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
        content = resp["choices"][0]["message"]["content"]
        meta = json.loads(content)
    except Exception as e:
        print(f"[WARN] GPT failed ({e}); using fallback metadata")
        meta = {
            "titulo": f"ASMR: {orig_title[:45]}",
            "descricao": "Vídeo ASMR gerado automaticamente para relaxar.",
        }
    meta["credit"] = src_url
    out = Path(tempfile.mkdtemp()) / "meta.json"
    out.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return out


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    vid = pick_video()
    if vid:
        url, title = vid["webpage_url"], vid["title"]
        print("[INFO] Selected YouTube:", title, url)
        src = safe_download_youtube(url)
        if not src:
            print("[WARN] YouTube download failed – switching to Pixabay.")
            tmpdir = Path(tempfile.mkdtemp())
            src, title, url = pixabay_download(tmpdir)
    else:
        tmpdir = Path(tempfile.mkdtemp())
        src, title, url = pixabay_download(tmpdir)

    clip  = vertical_crop(src)
    meta  = gen_meta(title, url)

    subprocess.run([sys.executable, "scripts/upload_youtube.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_instagram.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_tiktok.py", str(clip), str(meta)])

if __name__ == "__main__":
    main()

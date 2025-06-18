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

def pixabay_download(tmpdir: Path) -> Path:
    vid_id = random.choice(PIXABAY_IDS)
    url = f"https://cdn.pixabay.com/videvo_download/medium/{vid_id}.mp4"
    dst = tmpdir / "src.mp4"
    print("[INFO] Downloading fallback clip from Pixabay →", url)
    r = requests.get(url, timeout=60, stream=True)
    r.raise_for_status()
    with open(dst, "wb") as fp:
        for chunk in r.iter_content(chunk_size=1 << 16):
            fp.write(chunk)
    return dst, f"Pixabay clip {vid_id}", url

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
    prompt = textwrap.dedent(f"""
        Gere JSON com:
        - titulo (<=50 chars)
        - descricao (<=120 chars)
        Tema/Trigger: {orig_title!r}  (vídeo ASMR)
        Escrita em português.
    """)
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    meta   = json.loads(resp.choices[0].message.content)
    meta["credit"] = src_url
    mfile  = Path(tempfile.mkdtemp()) / "meta.json"
    mfile.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return mfile

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

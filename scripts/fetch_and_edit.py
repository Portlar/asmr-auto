#!/usr/bin/env python3
import os, subprocess, json, tempfile, random, time, sys
from pathlib import Path
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

# ── 1. Queries & fallback IDs ────────────────────────────────────────────────
SEARCH_QUERIES = [
    "asmr tapping",
    "asmr rain sounds",
    "asmr brushing microphone",
    "asmr keyboard",
    "asmr paper sounds",
    "asmr spray",
]

FALLBACK_VIDEO_IDS = [
    # CC-BY or CC-0 videos tested 2025-06-18
    "5qgJ-w2rGJM",  # Rain on tent – 10 h
    "x4eRcG5YY7I",  # Wood tapping
    "4fG0pRx6Q1k",  # Magazine page flipping
    "pDm3OziPbtA",  # Mechanical keyboard
    "2tmSQ0ap8Gc",  # Soft brush sounds
]

# ── 2. Helpers ───────────────────────────────────────────────────────────────
def yt_search_cc(query: str, n: int = 30):
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
        print(f"[WARN] yt-dlp search failed for query: {query!r}")
        return []

def pick_video():
    # 1) try live search
    for _ in range(6):  # 6 × random query
        vids = yt_search_cc(random.choice(SEARCH_QUERIES))
        if vids:
            return random.choice(vids)
    # 2) fallback list
    print("[INFO] All searches failed – using fallback CC video list.")
    vid_id = random.choice(FALLBACK_VIDEO_IDS)
    return {
        "webpage_url": f"https://www.youtube.com/watch?v={vid_id}",
        "title": f"Fallback video {vid_id}",
    }

def safe_download(url: str) -> Path:
    for attempt in range(5):
        tmp = Path(tempfile.mkdtemp())
        out = tmp / "src.mp4"
        try:
            subprocess.run(
                ["yt-dlp", "-f", "bv*+ba/best", "-o", str(out), url],
                check=True,
            )
            return out
        except subprocess.CalledProcessError:
            print(f"[WARN] yt-dlp failed (try {attempt+1}) – new video")
            url = pick_video()["webpage_url"]
            time.sleep(2)
    raise RuntimeError("All downloads failed.")

def vertical_crop(src: Path) -> Path:
    dst = src.with_name("final.mp4")
    subprocess.run(
        [
            "ffmpeg", "-i", str(src),
            "-ss", "0", "-t", "67",
            "-vf", "crop=in_h*9/16:in_h,scale=1080:1920",
            "-af", "loudnorm",
            "-y", str(dst),
        ],
        check=True,
    )
    return dst

def gen_meta(orig_title: str, src_url: str) -> Path:
    prompt = (
        "Crie JSON com 'titulo' (≤50 chars) e 'descricao' (≤120 chars) "
        f"em PT-BR para vídeo ASMR cujo gatilho é: {orig_title!r}"
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.6,
    )
    meta = json.loads(resp.choices[0].message.content)
    meta["credit"] = src_url
    p = Path(tempfile.mkdtemp()) / "meta.json"
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return p

# ── 3. Main ──────────────────────────────────────────────────────────────────
def main():
    v = pick_video()
    url, title = v["webpage_url"], v["title"]
    print("[INFO] video:", title, url)

    src = safe_download(url)
    clip = vertical_crop(src)
    meta = gen_meta(title, url)

    subprocess.run([sys.executable, "scripts/upload_youtube.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_instagram.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_tiktok.py", str(clip), str(meta)])

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os, subprocess, json, tempfile, random, time, sys
from pathlib import Path
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

SEARCH_QUERIES = [
    "asmr tapping",
    "asmr rain sounds",
    "asmr brushing microphone",
    "asmr keyboard",
    "asmr paper sounds",
    "asmr spray",
]

def yt_search_cc(query: str, n: int = 30):
    """
    Usa yt-dlp para buscar vídeos Creative Commons.
    Se o comando falhar (exit≠0), devolve lista vazia para forçar novo termo.
    """
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
        return []          # faz pick_video() tentar outro termo


def pick_video():
    for _ in range(5):
        vids = yt_search_cc(random.choice(SEARCH_QUERIES))
        if vids:
            return random.choice(vids)
    raise RuntimeError("No Creative-Commons ASMR video found.")

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
            print(f"[WARN] yt-dlp failed (try {attempt+1})")
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

def main():
    v = pick_video()
    url, title = v["webpage_url"], v["title"]
    print("[INFO] video:", title)
    src = safe_download(url)
    clip = vertical_crop(src)
    meta = gen_meta(title, url)
    subprocess.run([sys.executable, "scripts/upload_youtube.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_instagram.py", str(clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_tiktok.py", str(clip), str(meta)])

if __name__ == "__main__":
    main()

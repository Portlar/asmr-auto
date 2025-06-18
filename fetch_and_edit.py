#!/usr/bin/env python3
"""Baixa vídeo CC-BY do YouTube, corta para 67 s vertical, gera título PT-BR e posta."""
import os, subprocess, random, json, tempfile, sys
from pathlib import Path
import openai
from googleapiclient.discovery import build

YT_API_KEY = os.getenv("YT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

TMP_DIR = tempfile.mkdtemp()

def log(msg): print(msg, flush=True)

def search_cc_video(query="asmr tapping"):
    yt = build("youtube", "v3", developerKey=YT_API_KEY)
    req = yt.search().list(
        q=query,
        type="video",
        videoLicense="creativeCommon",
        videoDuration="any",
        part="id,snippet",
        maxResults=15
    )
    vids = req.execute()["items"]
    return random.choice(vids)

def download_video(video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    out = Path(TMP_DIR)/"src.mp4"
    subprocess.run(["yt-dlp", "-f", "bv+ba", "-o", str(out), url], check=True)
    return out

def cut_and_format(src):
    dst = Path(TMP_DIR)/"final.mp4"
    cmd = [
        "ffmpeg", "-i", str(src),
        "-ss", "00:00:05", "-t", "67",
        "-vf", "crop=in_h*9/16:in_h,scale=1080:1920",
        "-y", str(dst)
    ]
    subprocess.run(cmd, check=True)
    return dst

def gen_meta(original_title, source_url):
    prompt = f"Crie um título curto (até 50 caracteres) e uma descrição relaxante (100 caracteres) em português para um vídeo ASMR cujo gatilho é '{original_title}'. Devolva JSON com chaves titulo, descricao."
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}],
        temperature=0.7
    )
    data = json.loads(response.choices[0].message.content)
    data["credit"] = source_url
    meta_path = Path(TMP_DIR)/"meta.json"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return meta_path

def main():
    vid = search_cc_video()
    vid_id = vid["id"]["videoId"]
    title_orig = vid["snippet"]["title"]
    src = download_video(vid_id)
    final_clip = cut_and_format(src)
    meta = gen_meta(title_orig, f"https://www.youtube.com/watch?v={vid_id}")
    log(f"READY => {final_clip}\n{meta}")

    # Chamada de upload (placeholders)
    subprocess.run([sys.executable, "scripts/upload_youtube.py", str(final_clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_instagram.py", str(final_clip), str(meta)])
    subprocess.run([sys.executable, "scripts/upload_tiktok.py", str(final_clip), str(meta)])

if __name__ == "__main__":
    main()

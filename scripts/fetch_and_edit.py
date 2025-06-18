#!/usr/bin/env python3
"""
fetch_and_edit.py
─────────────────
1. Finds a random Creative-Commons ASMR video on YouTube (no API key needed).
2. Downloads it safely (retries if age-restricted).
3. Crops to 67-second vertical 1080×1920 and normalises audio.
4. Uses GPT-4o (OPENAI_API_KEY) to write a PT-BR title + description.
5. Calls uploader scripts (currently mock).
"""

import os, subprocess, json, tempfile, random, time, sys
from pathlib import Path
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG – tweak queries if you like
SEARCH_QUERIES = [
    "asmr tapping",
    "asmr rain sounds",
    "asmr brushing microphone",
    "asmr keyboard",
    "asmr paper sounds",
    "asmr spray",
]

# ──────────────────────────────────────────────────────────────────────────────
def yt_search_cc(query: str, max_results: int = 30):
    """
    Return a list of video dicts using yt-dlp's built-in search.
    No YouTube Data API key required.
    """
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query} creative commons",
        "--print-json",
        "--skip-download",
        "--no-playlist",
    ]
    output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    return [json.loads(line) for line in output.strip().splitlines()]


def pick_random_video():
    """Search until at least one

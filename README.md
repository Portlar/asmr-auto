# ASMR 67s Automation

Public GitHub repo template that:
1. Searches YouTube for Creative Commons ASMR videos
2. Downloads and converts them to a 67‑second vertical clip
3. Generates PT‑BR title/description with GPT‑4o
4. Uploads daily to YouTube Shorts, Instagram Reels and TikTok

## Quick start (<= 1 h)

```bash
git clone <your repo>
cd asmr_67s_auto
# optional test locally
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export YT_API_KEY=...
export OPENAI_API_KEY=...
python scripts/fetch_and_edit.py  # prints mock uploads
```

Then push to GitHub and add the following **Secrets**:

| Key | Value |
|-----|-------|
| `YT_API_KEY` | Your YouTube Data API key |
| `IG_TOKEN` | Instagram Graph token (with `publish_video`) |
| `IG_BUSINESS_ID` | Your IG Business ID |
| `TIKTOK_CLIENT_KEY` | TikTok Upload API client key |
| `TIKTOK_ACCESS_TOKEN` | TikTok Upload user token |
| `OPENAI_API_KEY` | Your OpenAI API key |

The Action `.github/workflows/asmr.yml` will run every day at 10:30 UTC.

**Note**: upload scripts are placeholders. Replace with real API code or keep them local if you only need the edited videos.

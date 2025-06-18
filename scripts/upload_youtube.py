import os, sys, json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1) Load OAuth token (must be in repo root)
creds_data = json.load(open("token.json"))
creds = Credentials(**creds_data)

# 2) Read inputs
video_file, meta_file = sys.argv[1], sys.argv[2]
meta = json.load(open(meta_file))

# 3) Build YouTube client
youtube = build("youtube", "v3", credentials=creds)

# 4) Upload as a Short
request = youtube.videos().insert(
  part="snippet,status",
  body={
    "snippet": {
      "title": meta["titulo"],
      "description": f"{meta['descricao']}\n\nCrédito original: {meta['credit']}",
      "tags": ["asmr","shorts"],
      "categoryId": "22"
    },
    "status": {"privacyStatus": "public"}
  },
  media_body=MediaFileUpload(video_file, mimetype="video/mp4", resumable=True)
)
response = request.execute()
print("✅ Uploaded Short ID:", response["id"])

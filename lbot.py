import json
import os
import requests
from datetime import date
import time

# ------------------------
# CONFIG
# ------------------------
ACCESS_TOKEN = "AQV2UUjkIU4d_V6fgXclh3_8mHQMsJkHUtDqONa5y9qhIwUIKX_2S-OettNRw-EzrT5Kr71veMKEaDxGk6ZySdFAMUNO4h9-nj1QqYV39n-U3pGc3NhFWO_ys0mv99FVPCmDpGxz7HpDJcGOb7qF5z5JSYm-cUUOocis5MhroNDeslFVoqu8-XPtZkoEXnwbAb-Vyl54QVft0ViSuwsSvnUg"
PERSON_URN = "urn:li:person:5jZN"  # put your LinkedIn access token here
POSTS_URL = "https://raw.githubusercontent.com/plateau11/lbot/main/posts.txt"
TRACK_FILE = "posted.json"
POSTS_PER_DAY = 3


# ------------------------
# FETCH POSTS.TXT
# ------------------------
def fetch_posts_from_github():
    resp = requests.get(POSTS_URL)
    resp.raise_for_status()
    content = resp.text

    raw_posts = content.split("===POST_START===")
    posts = []

    for raw in raw_posts:
        if "===POST_END===" in raw:
            body = raw.split("===POST_END===")[0].strip()

            if "===IMAGES===" in body:
                text, images_block = body.split("===IMAGES===")
                images = [line.strip() for line in images_block.splitlines() if line.strip()]
            else:
                text = body
                images = []

            if text.strip():
                posts.append({"text": text.strip(), "images": images})

    return posts


# ------------------------
# TRACKING
# ------------------------
def load_tracking():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_date": None, "last_index": -1}


def save_tracking(tracking):
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        json.dump(tracking, f)


def get_todays_posts(posts):
    tracking = load_tracking()
    today = str(date.today())

    if tracking["last_date"] == today:
        start_index = tracking["last_index"] - POSTS_PER_DAY + 1
        return posts[start_index:tracking["last_index"] + 1]

    start_index = tracking["last_index"] + 1
    end_index = start_index + POSTS_PER_DAY
    todays_posts = posts[start_index:end_index]

    if todays_posts:
        tracking["last_date"] = today
        tracking["last_index"] = end_index - 1
        save_tracking(tracking)

    return todays_posts


# ------------------------
# LINKEDIN API HELPERS
# ------------------------
def upload_image(image_url):
    """Upload external image to LinkedIn and return asset URN"""
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"

    register_body = {
        "registerUploadRequest": {
            "owner": PERSON_URN,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [
                {"identifier": "urn:li:userGeneratedContent", "relationshipType": "OWNER"}
            ],
            "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"]
        }
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    reg_resp = requests.post(register_url, headers=headers, json=register_body)
    reg_resp.raise_for_status()
    upload_info = reg_resp.json()

    upload_url = upload_info["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    asset_urn = upload_info["value"]["asset"]

    # Download image from GitHub/external link and upload
    img_data = requests.get(image_url).content
    up_resp = requests.put(upload_url, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, data=img_data)
    up_resp.raise_for_status()

    return asset_urn


def post_to_linkedin(text, image_urls=None):
    """Create a LinkedIn post with optional images"""
    image_assets = []
    if image_urls:
        for img_url in image_urls:
            try:
                asset = upload_image(img_url)
                image_assets.append({"status": "READY", "media": asset})
            except Exception as e:
                print(f"Image upload failed: {img_url}, {e}")

    post_url = "https://api.linkedin.com/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json"
    }

    post_data = {
        "author": PERSON_URN,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE" if image_assets else "NONE",
                "media": image_assets
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
    }

    resp = requests.post(post_url, headers=headers, json=post_data)
    print("Post response:", resp.status_code, resp.text)


# ------------------------
# MAIN
# ------------------------
if __name__ == "__main__":
    all_posts = fetch_posts_from_github()
    todays_posts = get_todays_posts(all_posts)

    if not todays_posts:
        print("✅ No more posts left.")
    else:
        for post in todays_posts:
            print("\nPublishing:", post["text"][:50], "...")
            post_to_linkedin(post["text"], post["images"])
            time.sleep(30)

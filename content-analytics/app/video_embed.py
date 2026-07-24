from typing import Any


def build_embed(platform: str, video_id: str, url: str) -> dict[str, Any]:
    platform = platform.lower()
    if platform == "youtube":
        if len(video_id) == 11 and video_id.replace("-", "").replace("_", "").isalnum():
            return {
                "type": "iframe",
                "src": f"https://www.youtube.com/embed/{video_id}",
            }
        return {"type": "link", "url": url or f"https://www.youtube.com/watch?v={video_id}"}

    if platform == "tiktok":
        return {
            "type": "iframe",
            "src": f"https://www.tiktok.com/embed/v2/{video_id}",
        }

    if platform == "instagram":
        return {"type": "instagram", "url": url}

    return {"type": "link", "url": url}

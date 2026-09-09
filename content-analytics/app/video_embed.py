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

    if platform == "vk":
        if "_" in video_id:
            owner_id, vk_video_id = video_id.split("_", 1)
            return {
                "type": "iframe",
                "src": f"https://vk.com/video_ext.php?oid={owner_id}&id={vk_video_id}",
            }
        return {"type": "link", "url": url}

    if platform == "dzen":
        return {"type": "link", "url": url or f"https://dzen.ru/shorts/{video_id}"}

    return {"type": "link", "url": url}

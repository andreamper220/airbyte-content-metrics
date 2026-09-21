from typing import Any

from app.dzen_meta import normalize_publication_id, shorts_player_url


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
        player_url = shorts_player_url(video_id, url)
        if not player_url:
            player_url = url or f"https://dzen.ru/shorts/{normalize_publication_id(video_id)}"
        # dzen.ru sets X-Frame-Options / CSP frame-ancestors, so iframe is blocked in browsers.
        return {"type": "link", "url": player_url}

    return {"type": "link", "url": url}

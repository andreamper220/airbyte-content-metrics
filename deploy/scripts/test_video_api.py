from app.db import query
from app.queries import VIDEO_CLICKS, VIDEO_COMMENTS, VIDEO_DETAIL

vid = query(
    "SELECT video_id, platform FROM analytics.mart_videos FINAL "
    "WHERE platform = 'youtube' ORDER BY published_at DESC LIMIT 1"
)
print("sample", vid)
if vid:
    p, i = vid[0]["platform"], vid[0]["video_id"]
    print("detail", query(VIDEO_DETAIL, {"platform": p, "video_id": i})[0].get("title"))
    try:
        print("clicks", query(VIDEO_CLICKS, {"platform": p, "video_id": i}))
    except Exception as exc:
        print("CLICKS_FAIL", type(exc), exc)
    try:
        print("comments", len(query(VIDEO_COMMENTS, {"platform": p, "video_id": i})))
    except Exception as exc:
        print("COMMENTS_FAIL", type(exc), exc)

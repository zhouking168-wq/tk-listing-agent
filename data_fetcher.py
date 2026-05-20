import os
import time
import requests
from dotenv import load_dotenv
from collections import Counter
import re

load_dotenv()

BRIGHT_DATA_API_KEY = os.getenv("BRIGHT_DATA_API_KEY")
POSTS_DATASET_ID = "gd_l1villgoiiidt09ci"
COMMENTS_DATASET_ID = "gd_lkf2st302ap89utw5k"
BASE_TRIGGER_URL = "https://api.brightdata.com/datasets/v3/trigger"
BASE_PROGRESS_URL = "https://api.brightdata.com/datasets/v3/progress"
BASE_SNAPSHOT_URL = "https://api.brightdata.com/datasets/v3/snapshot"

HEADERS = {
    "Authorization": f"Bearer {BRIGHT_DATA_API_KEY}",
    "Content-Type": "application/json",
}


def _trigger_collection(dataset_params: dict, input_data: list[dict]) -> str | None:
    """Trigger a Bright Data collection and return the snapshot_id."""
    print(f"[trigger] triggering collection...")
    try:
        resp = requests.post(
            BASE_TRIGGER_URL,
            headers=HEADERS,
            params=dataset_params,
            json=input_data,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        snapshot_id = data.get("snapshot_id")
        if not snapshot_id:
            print(f"[error] no snapshot_id: {data}")
            return None
        print(f"[trigger] snapshot_id: {snapshot_id}")
        return snapshot_id
    except requests.RequestException as e:
        print(f"[error] trigger failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[debug] {e.response.text[:500]}")
        return None


def _wait_for_snapshot(snapshot_id: str, max_retries: int = 5) -> dict | list | None:
    """Poll /progress/{id} until ready, then download /snapshot/{id}."""
    print(f"[wait] polling progress...")
    progress_url = f"{BASE_PROGRESS_URL}/{snapshot_id}"
    snapshot_url = f"{BASE_SNAPSHOT_URL}/{snapshot_id}"
    consecutive_errors = 0
    while True:
        try:
            resp = requests.get(progress_url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            consecutive_errors = 0
            status = resp.json().get("status")
            print(f"[status] {status}")
            if status == "ready":
                print(f"[download] downloading snapshot...")
                sr = requests.get(
                    snapshot_url,
                    headers=HEADERS,
                    params={"format": "json"},
                    timeout=60,
                )
                sr.raise_for_status()
                data = sr.json()
                if isinstance(data, list):
                    print(f"[ready] {len(data)} records")
                else:
                    print(f"[ready] data received")
                return data
            time.sleep(10)
        except requests.RequestException as e:
            consecutive_errors += 1
            print(f"[warn] request failed ({consecutive_errors}/{max_retries}): {e}")
            if consecutive_errors >= max_retries:
                print(f"[error] {max_retries} consecutive failures, giving up")
                return None
            time.sleep(10)


def _collect(query_params: dict, input_data: list[dict]) -> dict | list | None:
    """Full flow: trigger -> poll -> return data."""
    snapshot_id = _trigger_collection(query_params, input_data)
    if not snapshot_id:
        return None
    return _wait_for_snapshot(snapshot_id)


def search_posts_by_keyword(keyword: str, limit: int = 20) -> list[dict]:
    """
    Search TikTok posts by keyword via Bright Data.
    Searches profiles then extracts their top videos.

    Returns: [{"title": str, "tags": list, "play_count": int, "url": str}, ...]
    """
    print(f"[posts] keyword: {keyword}, limit: {limit}")
    try:
        result = _collect(
            {"dataset_id": POSTS_DATASET_ID, "type": "discover_new", "discover_by": "search_url"},
            [{"search_url": f"https://www.tiktok.com/search?q={keyword}", "country": "US"}],
        )
        if not result:
            print("[posts] no data")
            return []

        if isinstance(result, dict):
            profiles = result.get("data", result.get("profiles", []))
            if isinstance(profiles, dict):
                profiles = profiles.get("profiles", [])
        elif isinstance(result, list):
            profiles = result
        else:
            profiles = []

        if not isinstance(profiles, list):
            print(f"[posts] unexpected type: {type(profiles)}")
            return []

        output = []
        for profile in profiles:
            top_videos = profile.get("top_videos") or []
            top_posts = profile.get("top_posts_data") or []
            for i, video in enumerate(top_videos):
                if len(output) >= limit:
                    break
                post_info = top_posts[i] if i < len(top_posts) else {}
                tags = post_info.get("hashtags") or []
                output.append({
                    "title": post_info.get("description") or profile.get("nickname", ""),
                    "tags": tags if isinstance(tags, list) else [],
                    "play_count": video.get("playcount") or 0,
                    "url": video.get("video_url") or post_info.get("post_url", ""),
                })
            if len(output) >= limit:
                break

        print(f"[posts] got {len(output)} posts from {len(profiles)} profiles")
        return output
    except Exception as e:
        print(f"[error] search_posts_by_keyword failed: {e}")
        return []


def get_profile(username: str) -> dict | None:
    """
    Get TikTok profile info via Bright Data.

    Returns: {"followers": int, "engagement_rate": str, "top_videos": list} or None
    """
    print(f"[profile] username: @{username}")
    try:
        result = _collect(
            {"dataset_id": POSTS_DATASET_ID, "type": "url_collection"},
            [{"url": f"https://www.tiktok.com/@{username}"}],
        )
        if not result:
            print("[profile] no data")
            return None

        if isinstance(result, list):
            profile_data = result[0] if result else {}
        elif isinstance(result, dict):
            profile_data = result.get("data", result)
            if isinstance(profile_data, list):
                profile_data = profile_data[0] if profile_data else {}
        else:
            profile_data = {}

        if not profile_data:
            print("[profile] empty data")
            return None

        top_videos = profile_data.get("top_videos") or []
        output = {
            "followers": profile_data.get("followers") or 0,
            "engagement_rate": profile_data.get("awg_engagement_rate") or "",
            "top_videos": top_videos if isinstance(top_videos, list) else [],
        }
        print(f"[profile] @{username}: {output['followers']} followers, "
              f"{len(output['top_videos'])} top videos")
        return output
    except Exception as e:
        print(f"[error] get_profile failed: {e}")
        return None


def get_comments(product_url: str) -> list[dict]:
    """
    Get comments for a TikTok post (US).

    Returns: [{"text": str, "stars": int}, ...]
    """
    print(f"[comments] url: {product_url}")
    try:
        query_params = {"dataset_id": COMMENTS_DATASET_ID}
        input_data = [{"url": product_url}]
        result = _collect(query_params, input_data)
        if not result:
            print("[comments] no data")
            return []

        if isinstance(result, list):
            comments_data = result
        elif isinstance(result, dict):
            comments_data = result.get("data", result.get("comments", result.get("reviews", [])))
            if isinstance(comments_data, dict):
                comments_data = comments_data.get("comments", comments_data.get("reviews", []))
        else:
            print(f"[comments] unexpected type: {type(result)}")
            return []
        if not isinstance(comments_data, list):
            print(f"[comments] unexpected type: {type(comments_data)}")
            return []

        output = []
        for c in comments_data:
            output.append({
                "text": c.get("text", c.get("comment", c.get("content", ""))),
                "stars": c.get("stars", c.get("rating", c.get("score", 0))),
            })
        print(f"[comments] got {len(output)} comments")
        return output
    except Exception as e:
        print(f"[error] get_comments failed: {e}")
        return []


# ---------- Comment Analysis ----------

POSITIVE_WORDS = {
    "good", "great", "love", "comfortable", "high quality",
    "nice", "excellent", "amazing", "perfect", "beautiful",
    "soft", "durable", "worth", "recommend", "favorite",
}

NEGATIVE_WORDS = {
    "bad", "poor", "uncomfortable", "thin", "see through",
    "terrible", "horrible", "cheap", "ugly", "waste",
    "disappointed", "broken", "wrong", "small", "tight",
}


def _extract_keywords(text: str, word_set: set) -> list[str]:
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return [w for w in words if w in word_set]


def _extract_questions(text: str) -> list[str]:
    questions = []
    sentences = re.split(r"[.!]+", text)
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        has_qm = "?" in s
        has_qw = bool(re.search(
            r"\b(what|why|how|when|where|who|which|is it|does it|can i|should i|do you|will it)\b",
            s.lower(),
        ))
        if has_qm or has_qw:
            questions.append(s)
    return questions


def analyze_comments(comments: list[dict]) -> dict:
    """
    Analyze comment list.

    Returns:
    {
        "positive_keywords": [str, ...],
        "negative_keywords": [str, ...],
        "faqs": [str, ...],
    }
    """
    print(f"[analyze] analyzing {len(comments)} comments...")
    try:
        all_positive = []
        all_negative = []
        all_questions = []

        for c in comments:
            text = c.get("text", "")
            if not text:
                continue
            all_positive.extend(_extract_keywords(text, POSITIVE_WORDS))
            all_negative.extend(_extract_keywords(text, NEGATIVE_WORDS))
            all_questions.extend(_extract_questions(text))

        pos_counter = Counter(all_positive)
        neg_counter = Counter(all_negative)

        positive_keywords = [word for word, _ in pos_counter.most_common(5)]
        negative_keywords = [word for word, _ in neg_counter.most_common(5)]

        question_counter = Counter(all_questions)
        faqs = [q for q, _ in question_counter.most_common(10)]
        if len(faqs) < 3:
            faqs = (faqs + all_questions)[:3]

        result = {
            "positive_keywords": positive_keywords,
            "negative_keywords": negative_keywords,
            "faqs": faqs[:10],
        }
        print(f"[analyze] positive: {positive_keywords}")
        print(f"[analyze] negative: {negative_keywords}")
        print(f"[analyze] faqs: {len(faqs)}")
        return result
    except Exception as e:
        print(f"[error] analysis failed: {e}")
        return {"positive_keywords": [], "negative_keywords": [], "faqs": []}

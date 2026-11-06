#!/usr/bin/env python3
"""Sync Google Business Profile reviews to the website's reviews.json.

Credentials must be GitHub Actions secrets; never put them in web files or git.
Only verified locations accessible to the OAuth account can be queried.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://mybusiness.googleapis.com/v4"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVIEW_LINK = "https://g.page/r/CV3zzaoNa2YsEBM/review"
RATING = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def json_request(url, *, data=None, token=None, retries=3):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if data is not None:
        data = urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(retries):
        req = Request(url, data=data, headers=headers)
        try:
            with urlopen(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Google API returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Google API network error: {exc}") from exc


def get_access_token():
    values = {}
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if not value:
            raise RuntimeError(f"Missing GitHub Actions secret: {name}")
        values[name] = value
    response = json_request(TOKEN_URL, data={
        "client_id": values["GOOGLE_CLIENT_ID"],
        "client_secret": values["GOOGLE_CLIENT_SECRET"],
        "refresh_token": values["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    token = response.get("access_token")
    if not token:
        raise RuntimeError("Google did not return an OAuth access token")
    return token


def get_location_path():
    path = os.environ.get("GOOGLE_LOCATION_PATH", "").strip().strip("/")
    pieces = path.split("/")
    if len(pieces) != 4 or pieces[0] != "accounts" or pieces[2] != "locations" or not pieces[1] or not pieces[3]:
        raise RuntimeError("Set GOOGLE_LOCATION_PATH to accounts/ACCOUNT_ID/locations/LOCATION_ID (not a Google Maps Place ID)")
    if not all(part.replace("-", "").replace("_", "").isalnum() for part in (pieces[1], pieces[3])):
        raise RuntimeError("Invalid GOOGLE_LOCATION_PATH characters")
    return path


def fetch_all_reviews(token, location):
    reviews = []
    seen_pages = set()
    next_token = None
    count = None
    average = None
    while True:
        params = {"pageSize": 50, "orderBy": "updateTime desc"}
        if next_token:
            params["pageToken"] = next_token
        response = json_request(f"{API_BASE}/{location}/reviews?{urlencode(params)}", token=token)
        if count is None:
            count = response.get("totalReviewCount")
            average = response.get("averageRating")
        reviews.extend(response.get("reviews", []))
        next_token = response.get("nextPageToken")
        if not next_token:
            break
        if next_token in seen_pages:
            raise RuntimeError("Google returned a repeated review page token; refusing incomplete update")
        seen_pages.add(next_token)
    if count is None or average is None:
        raise RuntimeError("Google response did not include totalReviewCount and averageRating; leaving reviews.json unchanged")
    return reviews, int(count), float(average)


def normalize(review):
    reviewer = review.get("reviewer") or {}
    stars = review.get("starRating", "")
    rating = RATING.get(stars, stars if isinstance(stars, int) else 0)
    return {
        "review_id": review.get("reviewId", ""),
        "author_name": reviewer.get("displayName") or "Google reviewer",
        "rating": int(rating),
        "relative_time_description": (review.get("createTime") or "")[:10],
        "text": (review.get("comment") or "").strip(),
        "profile_photo_url": reviewer.get("profilePhotoUrl"),
        "time": review.get("createTime", ""),
        "google_review_url": REVIEW_LINK,
    }


def main():
    token = get_access_token()
    location = get_location_path()
    source, total_count, average_rating = fetch_all_reviews(token, location)
    # The overall rating/count include ALL reviews. Only text-bearing 5-star
    # reviews are displayed in the existing homepage's positive testimonial carousel.
    display = [normalize(r) for r in source]
    display = [r for r in display if r["rating"] == 5 and r["text"]]
    display.sort(key=lambda r: r["time"], reverse=True)
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Google Business Profile API",
        "average_rating": average_rating,
        "total_count": total_count,
        "display_count": f"{total_count} Google Reviews",
        "google_review_url": REVIEW_LINK,
        "count": len(display),
        "reviews": display,
    }
    # Never replace previously-good JSON with an empty or partial API response.
    if total_count > 0 and not source:
        raise RuntimeError("No review records returned for nonempty profile; refusing to overwrite")
    output = Path(__file__).resolve().parents[1] / "reviews.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {output.name}: Google rating {average_rating:.1f}, total {total_count}, displayed {len(display)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Review synchronization failed: {exc}", file=sys.stderr)
        sys.exit(1)

"""
fetch_reviews.py
Fetches all 5-star reviews for Lumen Dental from the Google Places API
and writes them to reviews.json in the repo root.

The Google Places Details API returns up to 5 reviews per call, but by
using different sort orders (most_relevant + newest) and combining the
results we can capture more. For a full unlimited pull you would need
the Google My Business API (requires OAuth) — this script gets the most
possible from the free Places API and de-duplicates by author name.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

API_KEY  = os.environ.get("GOOGLE_API_KEY", "")
PLACE_ID = "ChIJf7rQM5BBYIgRXfPNqg1rZiw"

FIELDS = "reviews,rating,user_ratings_total"
BASE   = "https://maps.googleapis.com/maps/api/place/details/json"


def fetch_reviews(sort_by):
    """Fetch reviews from Places API with the given sort order."""
    params = {
        "place_id":      PLACE_ID,
        "fields":        FIELDS,
        "reviews_sort":  sort_by,
        "key":           API_KEY,
        "language":      "en",
    }
    resp = requests.get(BASE, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "OK":
        print("  API status: {} - {}".format(data.get("status"), data.get("error_message","")))
        return []

    result  = data.get("result", {})
    reviews = result.get("reviews", [])
    print("  [{}] Got {} reviews from API".format(sort_by, len(reviews)))
    return reviews


def main():
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY secret not set.")
        sys.exit(1)

    print("Fetching reviews from Google Places API...")

    # Fetch both sort orders to maximise coverage (Places API cap is 5 per call)
    relevant = fetch_reviews("most_relevant")
    newest   = fetch_reviews("newest")

    # Merge, de-duplicate by author name (case-insensitive)
    seen   = set()
    merged = []
    for r in relevant + newest:
        key = r.get("author_name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(r)

    # Keep only 5-star reviews and normalise fields
    five_star = [
        {
            "author_name":               r.get("author_name", ""),
            "rating":                    r.get("rating", 5),
            "relative_time_description": r.get("relative_time_description", ""),
            "text":                      r.get("text", "").strip(),
            "profile_photo_url":         r.get("profile_photo_url", None),
            "time":                      r.get("time", 0),
        }
        for r in merged
        if r.get("rating", 0) >= 5 and r.get("text", "").strip()
    ]

    # Sort newest first
    five_star.sort(key=lambda r: r["time"], reverse=True)

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "place_id":   PLACE_ID,
        "count":      len(five_star),
        "reviews":    five_star,
    }

    with open("reviews.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Saved {} five-star reviews to reviews.json".format(len(five_star)))


if __name__ == "__main__":
    main()

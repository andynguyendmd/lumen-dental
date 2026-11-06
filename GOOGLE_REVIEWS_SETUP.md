# Google Business Profile Reviews — GitHub Pages setup

This repository's existing Places API job fetched at most a few reviews, wrote `count` as the number of displayed five-star reviews, and did not output `average_rating` or `total_count`. The homepage expects those last two fields.

This replacement uses **Google Business Profile API** and obtains the *actual total count* and *average rating*, collecting all pages of review data (up to 50 per request). It writes the public summary and selected real five-star text reviews to `reviews.json`, which the homepage already reads. This is a static GitHub Pages site: **never embed OAuth secrets in HTML or JavaScript.**

## Prerequisites

1. Own/manage the **verified** Lumen Dental Google Business Profile.
2. Create a Google Cloud project, request Google Business Profile API access/approval, and enable the necessary APIs. Instructions: https://developers.google.com/my-business/content/basic-setup
3. Set up OAuth 2.0 for `https://www.googleapis.com/auth/business.manage` with offline access. The account authorizing must manage the correct Google listing. Instructions: https://developers.google.com/my-business/content/implement-oauth
4. Generate a **refresh token** through your own approved Google Cloud OAuth client, with offline access. Keep it private. If your OAuth consent screen is in Testing mode, refresh tokens may expire after 7 days; configure the consent screen appropriately for durable use.
5. Find the Business Profile resource path `accounts/ACCOUNT_ID/locations/LOCATION_ID`. **This is not the Maps Place ID** in the old Python script. You can discover accounts with the Business Profile Account Management API and locations with Business Information API; the Google reviews v4 endpoint requires the `accounts/*/locations/*` path. Do not guess IDs.

## GitHub configuration

Go to **Repository → Settings → Secrets and variables → Actions**:

Create repository **Secrets**:
- `GOOGLE_CLIENT_ID` — your OAuth client ID
- `GOOGLE_CLIENT_SECRET` — your OAuth client secret
- `GOOGLE_REFRESH_TOKEN` — the refresh token

Create repository **Variable**:
- `GOOGLE_LOCATION_PATH` — `accounts/ACCOUNT_ID/locations/LOCATION_ID`

Never place these in Git, README, an issue, PR comment, or this chat.

In **Settings → Actions → General**, ensure GitHub Actions is enabled and workflows are allowed to create commits (`GITHUB_TOKEN` contents write permission). The job requests this permission explicitly. Branch rules must permit the bot to update `reviews.json`.

After merging the PR, run **Actions → Sync Google Business Profile reviews → Run workflow**. Once it succeeds, view `reviews.json`; it should contain `average_rating`, `total_count`, `reviews`, and `updated_at`. Scheduled runs occur once daily; GitHub does not guarantee an exact schedule time.

**If authorization fails**, the job fails without overwriting existing review data. The site can keep showing the existing hardcoded score until a successful sync, so check the workflow before trusting the displayed number.

For transparency, the *overall* score/count use all Google reviews; the carousel selectively displays text-bearing five-star reviews only. Each visitor can follow the Google link to see the complete review history.

Official API reference: https://developers.google.com/my-business/reference/rest/v4/accounts.locations.reviews/list

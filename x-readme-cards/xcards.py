import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUTS_DIR = ROOT / "outputs"
TWEETS_JSON = OUTPUTS_DIR / "tweets.json"
CARDS_MARKDOWN = OUTPUTS_DIR / "x-posts.md"

START = "<!-- X-POSTS:START -->"
END = "<!-- X-POSTS:END -->"

TWITTER_DATE = "%a %b %d %H:%M:%S %z %Y"
MIN_DATE = datetime.min.replace(tzinfo=timezone.utc)


def load_config() -> dict:
    config_path = ROOT / "config.json"

    if not config_path.exists():
        raise FileNotFoundError("Missing config.json")

    return json.loads(config_path.read_text())


def fetch_posts(config: dict, limit: int) -> None:
    from Scweet import Scweet

    OUTPUTS_DIR.mkdir(exist_ok=True)
    TWEETS_JSON.unlink(missing_ok=True)

    scweet = Scweet(cookies={"auth_token": config["auth_token"], "ct0": config["ct0"]})

    scweet.search(
        "from:" + config["username"],
        limit=limit,
        save=True,
        save_format="json",
        save_name="tweets.json",
    )


def parse_timestamp(post: dict) -> datetime:
    timestamp = post.get("timestamp") or post.get("raw", {}).get("legacy", {}).get("created_at")
    if not timestamp:
        return MIN_DATE

    try:
        return datetime.strptime(timestamp, TWITTER_DATE)
    except ValueError:
        return MIN_DATE


def load_posts(path: Path, limit: int) -> list[dict]:
    posts = json.loads(path.read_text())
    unique_posts = {}

    for post in posts:
        key = post.get("tweet_id") or post.get("tweet_url") or clean_text(post)
        unique_posts[key] = post

    posts = list(unique_posts.values())
    posts.sort(key=parse_timestamp, reverse=True)
    return list(reversed(posts[:limit]))


def media_urls(post: dict) -> list[str]:
    direct_links = post.get("media", {}).get("image_links") or []
    if direct_links:
        return direct_links

    legacy_media = (
        post.get("raw", {})
        .get("legacy", {})
        .get("extended_entities", {})
        .get("media", [])
    )
    return [
        media["media_url_https"]
        for media in legacy_media
        if media.get("type") == "photo" and media.get("media_url_https")
    ]


def clean_text(post: dict) -> str:
    text = html.unescape(post.get("text") or post.get("raw", {}).get("legacy", {}).get("full_text", ""))
    entities = post.get("raw", {}).get("legacy", {}).get("entities", {})

    for media in entities.get("media", []):
        if media.get("url"):
            text = text.replace(media["url"], "")

    for url in entities.get("urls", []):
        short_url = url.get("url")
        display_url = url.get("display_url") or url.get("expanded_url")
        if short_url and display_url:
            text = text.replace(short_url, display_url)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def short_text(text: str, max_chars: int = 240) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= max_chars:
        return one_line
    return one_line[: max_chars - 1].rstrip() + "..."


def format_count(count: int, singular: str, plural: str | None = None) -> str:
    label = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {label}"


def post_stats(post: dict) -> str:
    likes = int(post.get("likes") or 0)
    comments = int(post.get("comments") or 0)
    retweets = int(post.get("retweets") or 0)
    return " · ".join(
        [
            format_count(likes, "like"),
            format_count(comments, "reply", "replies"),
            format_count(retweets, "repost"),
        ]
    )


def post_date(post: dict) -> str:
    parsed = parse_timestamp(post)
    if parsed == MIN_DATE:
        return ""
    return f"{parsed:%b} {parsed.day}, {parsed:%Y}"


def render_post_card(post: dict) -> str:
    user = post.get("user", {})
    screen_name = user.get("screen_name") or "x"
    url = post.get("tweet_url") or f"https://x.com/{screen_name}/status/{post.get('tweet_id', '')}"
    images = media_urls(post)
    image_html = ""

    if images:
        image_html = (
            '<p align="center">'
            f'<a href="{html.escape(url)}">'
            f'<img src="{html.escape(images[0])}" alt="Post image" width="75%">'
            "</a>"
            "</p>"
        )

    text = clean_text(post)
    if images:
        text = short_text(text)

    body = html.escape(text).replace("\n", "<br>")
    meta = " · ".join(part for part in [post_date(post), post_stats(post)] if part)

    return "\n".join(
        [
            '<td width="33%" valign="top">',
            image_html,
            f'<sub>@{html.escape(screen_name)} · {html.escape(meta)}</sub><br><br>',
            body,
            "<br><br>",
            f'<strong><a href="{html.escape(url)}">View on X</a></strong>',
            "</td>",
        ]
    )


def render_markdown(posts: list[dict]) -> str:
    cards = "\n".join(render_post_card(post) for post in posts)
    return f'<table cellspacing="0" cellpadding="0">\n<tr>\n{cards}\n</tr>\n</table>\n'


def replace_marked_section(path: Path, content: str) -> None:
    existing = path.read_text()
    start = existing.find(START)
    end = existing.find(END)

    if start == -1 or end == -1 or start > end:
        raise ValueError(f"{path} must contain {START} and {END} markers")

    updated = existing[: start + len(START)] + "\n" + content.strip() + "\n" + existing[end:]
    path.write_text(updated)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent X posts and render three Markdown cards.")
    parser.add_argument("--no-fetch", action="store_true", help="Render from outputs/tweets.json without calling Scweet.")
    parser.add_argument("--limit", type=int, default=None, help="Number of cards to render.")
    parser.add_argument("--output", type=Path, default=CARDS_MARKDOWN, help="Markdown file to write.")
    parser.add_argument("--readme", type=Path, help="Optional Markdown file with X-POSTS markers to update.")
    args = parser.parse_args()

    config = load_config()
    limit = args.limit or int(config.get("max_posts", 3))

    if not args.no_fetch:
        fetch_posts(config, max(limit * 3, limit))

    posts = load_posts(TWEETS_JSON, limit)
    markdown = render_markdown(posts)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown)

    if args.readme:
        replace_marked_section(args.readme, markdown)

    print(f"Wrote {len(posts)} cards to {args.output}")


if __name__ == "__main__":
    main()

import argparse
import difflib
import hashlib
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
CARD_RE = re.compile(r"<td\b.*?</td>", re.DOTALL)


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

    for candidate in [TWEETS_JSON, ROOT / "tweets.json", Path.cwd() / "tweets.json"]:
        if candidate.exists():
            if candidate != TWEETS_JSON:
                TWEETS_JSON.write_bytes(candidate.read_bytes())
                candidate.unlink()
            return

    raise RuntimeError(f"Scweet did not create {TWEETS_JSON}")


def parse_timestamp(post: dict) -> datetime:
    timestamp = post.get("timestamp") or post.get("raw", {}).get("legacy", {}).get("created_at")
    if not timestamp:
        return MIN_DATE

    try:
        return datetime.strptime(timestamp, TWITTER_DATE)
    except ValueError:
        return MIN_DATE


def post_key(post: dict) -> str:
    return post.get("tweet_id") or post.get("tweet_url") or clean_text(post)


def screen_name(post: dict) -> str:
    return post.get("user", {}).get("screen_name") or ""


def is_reply(post: dict) -> bool:
    legacy = post.get("raw", {}).get("legacy", {})
    return any(
        legacy.get(field)
        for field in [
            "in_reply_to_status_id_str",
            "in_reply_to_user_id_str",
            "in_reply_to_screen_name",
        ]
    )


def is_retweet(post: dict) -> bool:
    legacy = post.get("raw", {}).get("legacy", {})
    return bool(legacy.get("retweeted_status_result") or legacy.get("retweeted_status_id_str"))


def is_profile_post(post: dict, username: str) -> bool:
    return (
        screen_name(post).lower() == username.lower()
        and not is_reply(post)
        and not is_retweet(post)
    )


def load_posts(path: Path, username: str, limit: int) -> tuple[list[dict], dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}. Run without --no-fetch to fetch posts first.")

    raw_posts = json.loads(path.read_text())
    unique_posts = {}

    for post in raw_posts:
        key = post_key(post)
        unique_posts[key] = post

    posts = list(unique_posts.values())
    profile_posts = [post for post in posts if is_profile_post(post, username)]
    profile_posts.sort(key=parse_timestamp, reverse=True)

    selected = profile_posts[:limit]
    stats = {
        "loaded": len(posts),
        "duplicates": len(raw_posts) - len(posts),
        "skipped_replies": sum(1 for post in posts if is_reply(post)),
        "skipped_retweets": sum(1 for post in posts if is_retweet(post)),
        "skipped_other_users": sum(1 for post in posts if screen_name(post).lower() != username.lower()),
        "eligible": len(profile_posts),
        "selected": len(selected),
    }
    return list(reversed(selected)), stats


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


def normalize_markup(content: str) -> str:
    return "\n".join(line.rstrip() for line in content.strip().splitlines())


def content_hash(content: str) -> str:
    return hashlib.sha256(normalize_markup(content).encode()).hexdigest()


def card_hashes(content: str) -> set[str]:
    return {content_hash(card) for card in CARD_RE.findall(content)}


def diff_sections(path: Path, current: str, updated: str) -> str:
    return "".join(
        difflib.unified_diff(
            normalize_markup(current).splitlines(keepends=True),
            normalize_markup(updated).splitlines(keepends=True),
            fromfile=f"{path}:current",
            tofile=f"{path}:new",
        )
    )


def replace_marked_section(
    path: Path,
    content: str,
    dry_run: bool = False,
    show_diff: bool = False,
) -> bool:
    existing = path.read_text()
    start = existing.find(START)
    end = existing.find(END)

    if start == -1 or end == -1 or start > end:
        raise ValueError(f"{path} must contain {START} and {END} markers")

    current = existing[start + len(START) : end]
    if content_hash(current) == content_hash(content):
        print("README cards unchanged.")
        return False

    current_hashes = card_hashes(current)
    updated_hashes = card_hashes(content)
    action = "would change" if dry_run else "changed"
    print(
        f"README cards {action}: "
        f"{len(updated_hashes - current_hashes)} new, "
        f"{len(current_hashes - updated_hashes)} removed"
    )

    if dry_run:
        if show_diff:
            print(diff_sections(path, current, content))
        print("No files changed.")
        return True

    updated = existing[: start + len(START)] + "\n" + content.strip() + "\n" + existing[end:]
    path.write_text(updated)
    return True


def print_selection(posts: list[dict], stats: dict[str, int], verbose: bool = False) -> None:
    if not verbose:
        print(f"Prepared {stats['selected']} README cards.")
        return

    print(
        "Loaded {loaded} posts; skipped {skipped_replies} replies, "
        "{skipped_retweets} retweets, {skipped_other_users} posts from other users; "
        "selected {selected} of {eligible} eligible profile posts.".format(**stats)
    )
    for post in posts:
        parsed = parse_timestamp(post)
        timestamp = "" if parsed == MIN_DATE else f"{parsed:%Y-%m-%d %H:%M:%S %z}"
        print(f"Selected {post_key(post)} {timestamp} {post.get('tweet_url', '')}".strip())


def snapshot_file(path: Path) -> bytes | None:
    if not path.exists():
        return None
    return path.read_bytes()


def restore_file(path: Path, content: bytes | None) -> None:
    if content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch recent X posts and render three Markdown cards.")
    parser.add_argument("--no-fetch", action="store_true", help="Render from outputs/tweets.json without calling Scweet.")
    parser.add_argument("--limit", type=int, default=None, help="Number of cards to render.")
    parser.add_argument("--output", type=Path, default=CARDS_MARKDOWN, help="Markdown file to write.")
    parser.add_argument("--readme", type=Path, help="Optional Markdown file with X-POSTS markers to update.")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files.")
    parser.add_argument("--show-diff", action="store_true", help="Show README card diff during dry runs.")
    parser.add_argument("--verbose", action="store_true", help="Show selected posts and filtering details.")
    args = parser.parse_args()

    config = load_config()
    limit = args.limit or int(config.get("max_posts", 3))

    original_tweets = snapshot_file(TWEETS_JSON) if args.dry_run and not args.no_fetch else None

    try:
        if not args.no_fetch:
            fetch_posts(config, max(limit * 6, limit))
            print("Fetched recent X posts.")
        else:
            print("Using cached X posts.")

        posts, stats = load_posts(TWEETS_JSON, config["username"], limit)
        markdown = render_markdown(posts)
        print_selection(posts, stats, verbose=args.verbose)

        if not args.dry_run:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown)

        if args.readme:
            replace_marked_section(
                args.readme,
                markdown,
                dry_run=args.dry_run,
                show_diff=args.show_diff,
            )

        if not args.dry_run:
            print(f"Generated {len(posts)} README cards.")
    finally:
        if args.dry_run and not args.no_fetch:
            restore_file(TWEETS_JSON, original_tweets)


if __name__ == "__main__":
    main()

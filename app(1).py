import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests
import streamlit as st


FEED_URL = "https://www.bbcgoodfood.com/feed"

st.set_page_config(
    page_title="BBC Good Food RSS Reader",
    page_icon="🍴",
    layout="wide",
)


def clean_html(value: str) -> str:
    """Convert a feed summary into readable plain text."""
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def format_date(entry) -> str:
    raw = entry.get("published") or entry.get("updated")
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%d %b %Y")
    except (TypeError, ValueError, IndexError):
        return raw[:40]


@st.cache_data(ttl=300, show_spinner=False)
def load_feed(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/130 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError("The feed returned invalid or unreadable XML.")
    return [
        {
            "title": entry.get("title", "Untitled"),
            "link": entry.get("link", ""),
            "summary": clean_html(entry.get("summary", "")),
            "date": format_date(entry),
            "author": entry.get("author", "BBC Good Food"),
        }
        for entry in parsed.entries
    ]


st.title("🍴 BBC Good Food RSS Reader")
st.caption("Latest articles from the BBC Good Food RSS feed")

with st.sidebar:
    st.header("Reader settings")
    search = st.text_input("Search articles", placeholder="Try pasta, chicken…")
    limit = st.slider("Articles to show", min_value=5, max_value=50, value=20, step=5)
    if st.button("Refresh feed", use_container_width=True):
        load_feed.clear()
        st.rerun()
    st.divider()
    st.caption(f"Source: {FEED_URL}")

try:
    articles = load_feed(FEED_URL)
except requests.HTTPError as exc:
    st.error(
        f"BBC Good Food did not allow the feed request ({exc.response.status_code}). "
        "Try again later or deploy the reader from a network that can access the feed."
    )
    st.stop()
except requests.RequestException as exc:
    st.error(f"Could not retrieve the feed: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Could not read the feed: {exc}")
    st.stop()

query = search.strip().lower()
if query:
    articles = [
        article
        for article in articles
        if query in f"{article['title']} {article['summary']}".lower()
    ]

articles = articles[:limit]
st.write(f"**{len(articles)} article(s)**")

if not articles:
    st.info("No articles match that search.")
else:
    for article in articles:
        with st.container(border=True):
            st.subheader(article["title"])
            meta = " · ".join(part for part in (article["date"], article["author"]) if part)
            if meta:
                st.caption(meta)
            if article["summary"]:
                st.write(article["summary"])
            if article["link"]:
                st.link_button("Read article", article["link"])


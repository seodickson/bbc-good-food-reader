import html
import re
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

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
    raw = entry.get("date", "")
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).strftime("%d %b %Y")
    except (TypeError, ValueError, IndexError):
        return raw[:40]


def text_from_element(element, names):
    """Find text from RSS or Atom elements, including namespaced tags."""
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in names and child.text:
            return child.text.strip()
    return ""


def image_from_element(element):
    """Find an image URL from common RSS media and enclosure fields."""
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        url = child.attrib.get("url", "")
        if tag in {"content", "thumbnail", "image"} and url:
            return url
        if tag == "enclosure" and child.attrib.get("type", "").startswith("image/"):
            return child.attrib.get("url", "")
    return ""


def parse_feed(content: bytes):
    root = ElementTree.fromstring(content)
    items = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in {"item", "entry"}:
            continue

        link = text_from_element(element, {"link"})
        if not link:
            for child in list(element):
                if child.tag.rsplit("}", 1)[-1] == "link":
                    link = child.attrib.get("href", "")
                    break

        items.append(
            {
                "title": text_from_element(element, {"title"}) or "Untitled",
                "link": link,
                "summary": clean_html(
                    text_from_element(
                        element,
                        {"description", "summary", "content", "encoded"},
                    )
                ),
                "image": image_from_element(element),
                "date": text_from_element(
                    element, {"pubDate", "published", "updated", "date"}
                ),
                "author": text_from_element(element, {"author", "creator"})
                or "BBC Good Food",
            }
        )
    return items


@st.cache_data(ttl=300, show_spinner=False)
def load_feed(url: str):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/130 Safari/537.36"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return parse_feed(response.read())


st.title("🍴 BBC Good Food RSS Reader")
st.markdown(
    "Browse the latest recipes, cooking advice and food features from BBC Good Food. "
    "Use the search box to find articles by title or description."
)
st.caption("The feed refreshes automatically every five minutes while this page is open.")

with st.sidebar:
    st.header("Reader settings")
    search = st.text_input("Search articles", placeholder="Try pasta, chicken…")
    limit = st.slider("Articles to show", min_value=5, max_value=50, value=20, step=5)
    if st.button("Refresh feed", use_container_width=True):
        load_feed.clear()
        st.rerun()
    st.divider()
    st.caption(f"Source: {FEED_URL}")

@st.fragment(run_every="5m")
def display_feed():
    try:
        articles = load_feed(FEED_URL)
    except HTTPError as exc:
        st.error(
            f"BBC Good Food did not allow the feed request ({exc.code}). "
            "Try again later or deploy the reader from a network that can access the feed."
        )
        return
    except URLError as exc:
        st.error(f"Could not retrieve the feed: {exc}")
        return
    except Exception as exc:
        st.error(f"Could not read the feed: {exc}")
        return

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
                image_url = article.get("image", "")
                if image_url:
                    st.image(image_url, use_container_width=True)
                st.subheader(article["title"])
                meta = " · ".join(
                    part for part in (article["date"], article["author"]) if part
                )
                if meta:
                    st.caption(meta)
                if article["summary"]:
                    st.write(article["summary"])
                if article["link"]:
                    st.link_button("Read article", article["link"])


display_feed()

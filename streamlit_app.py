import os
import json
import requests
import streamlit as st
from groq import Groq

# ----------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="News Verifier",
    page_icon="📰",
    layout="wide",
)

# ----------------------------------------------------------------------
# API keys
# On Streamlit Community Cloud, set these under:
#   App settings -> Secrets, as:
#     NEWS_API_KEY = "..."
#     GROQ_API_KEY = "..."
# Locally, create a file .streamlit/secrets.toml with the same two lines.
# ----------------------------------------------------------------------
NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", os.getenv("NEWS_API_KEY"))
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

if not NEWS_API_KEY or not GROQ_API_KEY:
    st.error(
        "Missing API keys. Add NEWS_API_KEY and GROQ_API_KEY in "
        "Streamlit secrets (App settings -> Secrets) before using the app."
    )
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# ----------------------------------------------------------------------
# Sidebar navigation (replaces Flask's /, /inspect, /about routes)
# ----------------------------------------------------------------------
st.sidebar.title("📰 News Verifier")
page = st.sidebar.radio("Navigate", ["Home", "Inspect", "About"])

CATEGORIES = ["Politics", "Sports", "Technology", "Business", "Entertainment", "Health"]

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_articles(category: str | None):
    url = (
        "https://newsapi.org/v2/everything?"
        "language=en&"
        "sortBy=publishedAt&"
        "pageSize=30&"
        "domains=thehindu.com,ndtv.com,indiatimes.com,indianexpress.com,moneycontrol.com&"
        f"apiKey={NEWS_API_KEY}"
    )
    if category:
        url += f"&q={category}"

    response = requests.get(url, timeout=15).json()
    articles = response.get("articles", [])

    selected = []
    titles = set()
    for article in articles:
        title = article.get("title")
        if not title or title in titles:
            continue
        titles.add(title)
        selected.append(
            {
                "title": title,
                "description": article.get("description"),
                "url": article.get("url"),
                "image": article.get("urlToImage"),
            }
        )
        if len(selected) == 6:
            break
    return selected


def verify_news(headline: str, description: str, url: str):
    prompt = f"""
You are an Indian news verification AI.
Your job is to check whether the following news is Real, Fake, Misleading, or Uncertain.
===== NEWS SUBMISSION =====
Headline: {headline}
Description: {description}
URL: {url}
===========================
Instructions:
1. Analyse the news carefully.
2. Compare with reliable information from trusted Indian news agencies and official government sources.
3. If the claim cannot be verified, say so clearly.
4. If it is misleading or fake, explain why.
5. Return ONLY valid JSON in the following format:
{{
    "status": "Real | Fake | Misleading | Uncertain",
    "confidence": "High | Medium | Low",
    "explanation": "",
    "most_likely_truth": "",
    "potential_harms": "",
    "required_missing_details": "",
    "sources": [
        ""
    ]
}}
"""
    try:
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-instruct-0905",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": raw}
    except Exception as e:
        return {"error": str(e)}


STATUS_COLOR = {
    "Real": "🟢",
    "Fake": "🔴",
    "Misleading": "🟠",
    "Uncertain": "⚪",
}

# ----------------------------------------------------------------------
# HOME page  (was: @app.route("/"))
# ----------------------------------------------------------------------
if page == "Home":
    st.title("📰 Latest News")

    cols = st.columns(len(CATEGORIES) + 1)
    if "category" not in st.session_state:
        st.session_state.category = None

    if cols[0].button("All", use_container_width=True):
        st.session_state.category = None
    for i, cat in enumerate(CATEGORIES, start=1):
        if cols[i].button(cat, use_container_width=True):
            st.session_state.category = cat

    with st.spinner("Fetching latest articles..."):
        articles = fetch_articles(st.session_state.category)

    if not articles:
        st.info("No articles found. Try a different category.")
    else:
        grid = st.columns(3)
        for i, art in enumerate(articles):
            with grid[i % 3]:
                if art["image"]:
                    st.image(art["image"], use_container_width=True)
                st.subheader(art["title"])
                if art["description"]:
                    st.write(art["description"])
                st.markdown(f"[Read full article]({art['url']})")
                st.divider()

# ----------------------------------------------------------------------
# INSPECT page  (was: @app.route("/inspect"))
# ----------------------------------------------------------------------
elif page == "Inspect":
    st.title("🔍 Inspect a News Claim")
    st.write("Paste a headline, description, and/or source URL to check its credibility.")

    with st.form("inspect_form"):
        headline = st.text_input("Headline")
        description = st.text_area("Description")
        url = st.text_input("Source URL")
        submitted = st.form_submit_button("Verify")

    if submitted:
        if not headline and not description and not url:
            st.warning("Enter at least a headline, description, or URL.")
        else:
            with st.spinner("Analysing with AI..."):
                result = verify_news(headline, description, url)

            if "error" in result:
                st.error("Couldn't parse a clean verdict. Raw model output below:")
                st.code(result["error"])
            else:
                status = result.get("status", "Uncertain")
                confidence = result.get("confidence", "Low")
                st.markdown(f"## {STATUS_COLOR.get(status, '⚪')} {status}  ·  Confidence: {confidence}")

                st.markdown("**Explanation**")
                st.write(result.get("explanation", "—"))

                st.markdown("**Most likely truth**")
                st.write(result.get("most_likely_truth", "—"))

                st.markdown("**Potential harms if false**")
                st.write(result.get("potential_harms", "—"))

                st.markdown("**Missing details needed to verify further**")
                st.write(result.get("required_missing_details", "—"))

                sources = result.get("sources", [])
                if sources:
                    st.markdown("**Sources**")
                    for s in sources:
                        if s:
                            st.markdown(f"- {s}")

# ----------------------------------------------------------------------
# ABOUT page  (was: @app.route("/about"))
# ----------------------------------------------------------------------
else:
    st.title("About News Verifier")
    st.write(
        "News Verifier pulls recent headlines from trusted Indian news domains "
        "and uses an AI model to flag whether a given news claim looks Real, "
        "Fake, Misleading, or Uncertain, along with a plain-language explanation."
    )
    st.write("Built with Streamlit, NewsAPI, and Groq.")

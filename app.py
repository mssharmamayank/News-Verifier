import os
import json
import requests
from flask import Flask, render_template, request
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# API Keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq Client
client = Groq(api_key=GROQ_API_KEY)


@app.route("/")
def home():
    category = request.args.get("category", None)

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

    response = requests.get(url).json()
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

    return render_template(
        "home.html",
        articles=selected,
        active_category=category,
    )


@app.route("/inspect", methods=["GET", "POST"])
def inspect():
    result = None

    if request.method == "POST":
        headline = request.form.get("headline", "")
        description = request.form.get("description", "")
        url = request.form.get("url", "")

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
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            raw = response.choices[0].message.content

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {"error": raw}

        except Exception as e:
            result = {"error": str(e)}

    return render_template("inspect.html", result=result)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
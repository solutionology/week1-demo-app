"""Retrieve bounded web excerpts for either LLM through the Tavily Search API."""
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests


class SearchError(Exception):
    """Safe search failure without request headers or response bodies."""


def search_customer(settings, name, website):
    if not settings.search_api_key:
        raise SearchError("Web search requires TAVILY_API_KEY in .env or deployment secrets. Add it, or turn off Search the web for an offline run.")
    domain = urlsplit(website).hostname
    query = f"{name} {domain} company products services customers business model"
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {settings.search_api_key}"},
            json={"query": query, "search_depth": "basic", "topic": "general",
                  "max_results": settings.search_max_results,
                  "include_answer": False, "include_raw_content": False},
            timeout=(10, settings.search_timeout), allow_redirects=False,
        )
        if response.status_code != 200:
            hint = {401: "Check TAVILY_API_KEY.", 403: "Check Tavily account access.",
                    429: "Search is rate limited; try again later.",
                    432: "Check your Tavily usage limit.",
                    433: "Check your Tavily usage limit."}.get(
                        response.status_code, "Try again later or check your Tavily account.")
            raise SearchError(f"Web search returned HTTP {response.status_code}. {hint}")
        body = response.json()
        rows = body.get("results") if isinstance(body, dict) else None
        if not isinstance(rows, list):
            raise ValueError
    except requests.Timeout:
        raise SearchError("Web search timed out. Try again or increase SEARCH_TIMEOUT.") from None
    except requests.RequestException:
        raise SearchError("Cannot reach Tavily web search. Check your internet connection.") from None
    except ValueError:
        raise SearchError("Web search returned an invalid response. Please try again.") from None

    sources, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        url, content = row.get("url"), row.get("content")
        if not isinstance(url, str) or not isinstance(content, str) or not content.strip():
            continue
        try:
            parsed = urlsplit(url)
            if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                    or parsed.username or parsed.password or any(c.isspace() for c in url)):
                continue
        except ValueError:
            continue
        if url in seen or len(url) > 2048:
            continue
        seen.add(url)
        title = row.get("title")
        sources.append({"id": len(sources) + 1,
                        "title": title[:200] if isinstance(title, str) and title else parsed.hostname,
                        "url": url, "excerpt": content.strip()[:1800]})
        if len(sources) >= settings.search_max_results:
            break
    if not sources:
        raise SearchError("Web search returned no usable sources. Check the customer details or turn off Search the web for an offline run.")
    return {"query": query, "retrieved_at": datetime.now(timezone.utc).isoformat(), "sources": sources}

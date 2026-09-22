"""Web search and page fetching for the model's research tools.

No API key is required by default: DuckDuckGo HTML is used, falling back to the
Wikipedia API.  Optional backends (SearXNG, Tavily) can be configured in
``config['web']``.
"""

import html
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) HaiLPER/1.0 "
              "(+https://github.com/tsb47/hailper)")
MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 12


class WebError(Exception):
    pass


def _get(url, timeout=DEFAULT_TIMEOUT, headers=None):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*"})
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_BYTES)
    except urllib.error.HTTPError as error:
        raise WebError("HTTP %s from %s" % (error.code, url))
    except urllib.error.URLError as error:
        raise WebError("Could not reach %s: %s" % (url, error.reason))
    except socket.timeout:
        raise WebError("Request to %s timed out." % url)
    return data.decode("utf-8", "replace")


def _strip_html(text):
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def _ddg_url(href):
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("uddg"):
            return query["uddg"][0]
    return href


def _parse_ddg_lite(page):
    links = []
    for match in re.finditer(
            r'<a[^>]*href="([^"]+)"[^>]*class=[\'"]result-link[\'"][^>]*>(.*?)</a>',
            page, re.DOTALL):
        links.append((_ddg_url(html.unescape(match.group(1))),
                      _strip_html(match.group(2))))
    snippets = [_strip_html(match.group(1)) for match in re.finditer(
        r'class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', page, re.DOTALL)]
    results = []
    for index, (link, title) in enumerate(links):
        if title and link:
            results.append({
                "title": title, "url": link,
                "snippet": snippets[index] if index < len(snippets) else ""})
        if len(results) >= 5:
            break
    return results


def _parse_ddg_html(page):
    results = []
    for match in re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            page, re.DOTALL):
        title = _strip_html(match.group(2))
        link = _ddg_url(html.unescape(match.group(1)))
        if title and link:
            results.append({"title": title, "url": link, "snippet": ""})
        if len(results) >= 5:
            break
    return results


def _search_duckduckgo(query, timeout):
    results = []
    try:
        page = _get("https://lite.duckduckgo.com/lite/?q="
                    + urllib.parse.quote(query), timeout)
        results = _parse_ddg_lite(page)
    except WebError:
        results = []
    if not results:
        try:
            page = _get("https://html.duckduckgo.com/html/?q="
                        + urllib.parse.quote(query), timeout)
            results = _parse_ddg_html(page)
        except WebError:
            results = []
    return results


def _search_wikipedia(query, timeout):
    url = ("https://en.wikipedia.org/w/api.php?action=query&list=search"
           "&format=json&srlimit=5&srsearch=" + urllib.parse.quote(query))
    data = json.loads(_get(url, timeout))
    results = []
    for item in (data.get("query") or {}).get("search") or []:
        title = item.get("title") or ""
        results.append({
            "title": title,
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                title.replace(" ", "_")),
            "snippet": _strip_html(item.get("snippet") or ""),
        })
    return results


def _search_searxng(query, base_url, timeout):
    url = base_url.rstrip("/") + "/search?format=json&q=" + urllib.parse.quote(query)
    data = json.loads(_get(url, timeout))
    results = []
    for item in (data.get("results") or [])[:5]:
        results.append({"title": item.get("title") or "",
                        "url": item.get("url") or "",
                        "snippet": item.get("content") or ""})
    return results


def search(query, config=None, timeout=DEFAULT_TIMEOUT):
    """Return a list of {title, url, snippet} dicts."""
    query = (query or "").strip()
    if not query:
        return []
    config = config or {}
    web = config.get("web") or {}
    backend = (web.get("backend") or "auto").lower()
    errors = []
    try:
        if backend == "searxng" and web.get("base_url"):
            return _search_searxng(query, web["base_url"], timeout)
        if backend in ("duckduckgo", "auto"):
            results = _search_duckduckgo(query, timeout)
            if results:
                return results
        if backend in ("wikipedia", "auto"):
            return _search_wikipedia(query, timeout)
    except WebError as error:
        errors.append(str(error))
    except Exception as error:  # noqa: BLE001
        errors.append(str(error))
    if errors:
        raise WebError(errors[0])
    return []


def fetch(url, max_chars=4000, timeout=DEFAULT_TIMEOUT):
    """Fetch a URL and return readable plain text."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebError("Only http/https URLs are allowed.")
    page = _get(url, timeout)
    text = _strip_html(page)
    return text[:max_chars] if text else "(no readable text)"


def format_results(results):
    lines = []
    for index, item in enumerate(results, 1):
        lines.append("%d. %s\n   %s\n   %s"
                     % (index, item.get("title", ""), item.get("url", ""),
                        item.get("snippet", "")))
    return "\n".join(lines) if lines else "(no results)"

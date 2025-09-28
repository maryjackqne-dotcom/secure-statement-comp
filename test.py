#!/usr/bin/env python3
"""
Paste cookie-like text (lines or whitespace/tab separated). Produces cookies.json
Each cookie will have: name, value, domain, path, url
"""
import json
import re
from urllib.parse import urlparse

URL_RE = re.compile(r"^https?://", re.IGNORECASE)

def is_url(token: str) -> bool:
    return bool(URL_RE.match(token))

def extract_domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc or ""

def looks_like_value(token: str) -> bool:
    # numeric timestamps, or long base64-like strings often used as cookie values
    if re.fullmatch(r"[\d\.]+", token):
        return True
    if len(token) > 20 and re.fullmatch(r"[A-Za-z0-9_\-+/=\.]+", token):
        return True
    return False

def parse_cookies(raw_text: str):
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    cookies = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = re.split(r"\s+", line)
        url_token = next((p for p in parts if is_url(p)), None)

        if len(parts) >= 2:
            name = parts[0]
            # if last token is the URL, there's no explicit value on this line
            last = parts[-1]
            value = "" if (url_token and last == url_token) else last
            url = url_token or ""
            domain = extract_domain(url) if url else ""
            cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "url": url
            })
            i += 1
            continue

        # single-token line: could be a name OR a value; lookahead to decide
        token = parts[0]
        next_line = lines[i+1].strip() if (i+1) < len(lines) else None
        if next_line:
            next_parts = re.split(r"\s+", next_line)
            if len(next_parts) == 1 and looks_like_value(next_parts[0]):
                # treat current token as name, next line as its value
                name = token
                value = next_parts[0]
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": "",
                    "path": "/",
                    "url": ""
                })
                i += 2  # skip next line (we consumed it as value)
                continue

        # otherwise: if previous cookie exists and has empty value, assume this token is its value
        if cookies and cookies[-1].get("value", "") == "":
            cookies[-1]["value"] = token
        else:
            # otherwise create a cookie with this token as name (no url/value known)
            cookies.append({
                "name": token,
                "value": "",
                "domain": "",
                "path": "/",
                "url": ""
            })
        i += 1

    return cookies

if __name__ == "__main__":
    print("Paste your cookie text (end with Ctrl+D / Ctrl+Z):")
    raw_input = ""
    try:
        while True:
            raw_input += input() + "\n"
    except EOFError:
        pass

    parsed = parse_cookies(raw_input)
    with open("cookies.json", "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=4, ensure_ascii=False)

    print("✅ Saved cookies.json with 'url' field added.")

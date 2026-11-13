"""Generate an SVG of language usage across the user's public, original repos.

Percentages are based on bytes of code reported by GitHub's languages API.
Requires only Python's standard library.
"""

import hashlib
import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USERNAME = "tandaianxle"
OUTPUT = Path(__file__).resolve().parent / "languages.svg"

COLORS = {
    "Python": "#F4C542",      # Golden yellow
    "C": "#2F81F7",           # Blue
    "JavaScript": "#F97316",  # Orange
    "HTML": "#E34F26",        # Red
    "CSS": "#8B5CF6",         # Purple
}
FALLBACK_COLORS = (
    "#22C55E", "#06B6D4", "#E879F9", "#FACC15", "#FB7185", "#14B8A6"
)


def api_get(url):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-profile-language-bar",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub API request failed: {url}: {error}") from error


def fetch_language_totals():
    totals = Counter()
    page = 1
    while True:
        repos = api_get(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
        )
        if not isinstance(repos, list):
            raise RuntimeError(f"Unexpected repository response: {repos}")
        for repo in repos:
            if repo.get("fork") or repo.get("name", "").lower() == USERNAME.lower():
                continue
            # Language API returns a dictionary of code bytes by language.
            languages = api_get(repo["languages_url"])
            totals.update({lang: count for lang, count in languages.items() if count > 0})
        if len(repos) < 100:
            break
        page += 1
    return totals


def color_for(language):
    if language in COLORS:
        return COLORS[language]
    index = int(hashlib.sha256(language.encode("utf-8")).hexdigest()[:8], 16)
    return FALLBACK_COLORS[index % len(FALLBACK_COLORS)]


def generate_svg(totals):
    languages = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    total_bytes = sum(totals.values())
    n_rows = (len(languages) + 1) // 2
    height = max(156, 124 + n_rows * 33)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" role="img" aria-labelledby="heading description">',
        f'<title id="heading">Languages used in my projects</title>',
        f'<desc id="description">Share of code by language across public, non-fork GitHub repositories, measured by bytes.</desc>',
        f'<rect x="0.5" y="0.5" width="839" height="{height - 1}" rx="14" fill="#0D1117" stroke="#30363D"/>',
        '<text x="24" y="35" fill="#E6EDF3" font-family="Arial, sans-serif" font-size="19" font-weight="bold">Languages in my projects</text>',
        '<text x="24" y="57" fill="#8B949E" font-family="Arial, sans-serif" font-size="12">All public, original repositories · by code bytes</text>',
        '<rect x="24" y="73" width="792" height="22" rx="6" fill="#21262D"/>',
    ]
    if total_bytes == 0:
        parts.append('<text x="24" y="125" fill="#8B949E" font-family="Arial, sans-serif" font-size="14">No public project code detected yet.</text>')
    else:
        clip = '<clipPath id="bar-clip"><rect x="24" y="73" width="792" height="22" rx="6"/></clipPath>'
        parts.append(f'<defs>{clip}</defs><g clip-path="url(#bar-clip)">')
        cursor = 24.0
        for i, (language, count) in enumerate(languages):
            width = 816.0 - cursor if i == len(languages) - 1 else 792 * count / total_bytes
            parts.append(f'<rect x="{cursor:.3f}" y="73" width="{width:.3f}" height="22" fill="{color_for(language)}"/>')
            cursor += width
        parts.append('</g>')
        for i, (language, count) in enumerate(languages):
            column = i % 2
            row = i // 2
            x = 24 + 410 * column
            y = 124 + 33 * row
            safe_language = html.escape(language)
            percent = 100 * count / total_bytes
            parts.append(f'<rect x="{x}" y="{y - 12}" width="13" height="13" rx="3" fill="{color_for(language)}"/>')
            parts.append(f'<text x="{x + 23}" y="{y}" fill="#E6EDF3" font-family="Arial, sans-serif" font-size="14">{safe_language}</text>')
            parts.append(f'<text x="{x + 365}" y="{y}" text-anchor="end" fill="#8B949E" font-family="Arial, sans-serif" font-size="14">{percent:.1f}%</text>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def main():
    totals = fetch_language_totals()
    OUTPUT.write_text(generate_svg(totals), encoding="utf-8")
    print(f"Updated {OUTPUT} using {sum(totals.values())} bytes across {len(totals)} languages")


if __name__ == "__main__":
    main()

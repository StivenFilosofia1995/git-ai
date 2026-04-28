import os

path = "app/services/event_fallback_discovery.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Make sure we use ddgs and not duckduckgo_search anywhere if it appears, but it already uses ddgs.
# We just need to change the call back to _google_search_urls instead of the browser one that failed to find elements.
text = text.replace('urls = await _search_urls_with_browser(query, max_results=max_results_per_query)', 'urls = await _google_search_urls(query, max_results=max_results_per_query)')

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated event_fallback_discovery.py")

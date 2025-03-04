# utils/serpapi_helpers.py
import requests
import time
import datetime
import re
from analysis_helpers import parse_video_length, parse_view_count
import os

def clean_query(q: str) -> str:
    q = q.strip(' "')
    return re.sub(r'^[0-9]+\.\s*', '', q).strip()

def serpapi_google_trend(query: str, api_key: str, timeframe: str = "today 12-m", gprop: str = "youtube") -> float:
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_trends",
        "q": query,
        "api_key": api_key,
        "timeframe": timeframe,
        "gprop": gprop,
    }
    r = requests.get(url, params=params)
    data = r.json()

    timeline_data = data.get("interest_over_time", {}).get("timeline_data", [])
    if not timeline_data:
        return 0.0

    values = []
    for item in timeline_data:
        list_of_values = item.get("values", [])
        for v in list_of_values:
            if "extracted_value" in v:
                values.append(int(v["extracted_value"]))
            else:
                raw_val = v.get("value", "0")
                try:
                    val_int = int(raw_val)
                except:
                    val_int = 0
                values.append(val_int)
    if not values:
        return 0.0

    avg_popularity = sum(values) / len(values)
    return float(avg_popularity)

def get_google_trends_for_queries(queries, timeframe="now 7-d", geo="US"):
    """
    Fetches Google Trends data for a list of queries.

    Args:
        queries (list): List of search queries.
        timeframe (str): Timeframe for trends data (default is last 7 days).
        geo (str): Geographic location (default is United States).

    Returns:
        dict: A dictionary mapping each query to its trend data.
    """
    trends_data = {}
    for query in queries:
        data = fetch_trends_from_api(query, timeframe, geo)
        trends_data[query] = data
    return trends_data

def fetch_trends_from_api(query, timeframe, geo):
    """
    Placeholder function to simulate fetching trends data from an API.

    Args:
        query (str): The search query.
        timeframe (str): The timeframe for trends data.
        geo (str): The geographic location.

    Returns:
        dict: Simulated trends data.
    """
    # Replace this with actual API integration
    return {
        "query": query,
        "trend_score": 75  # Example score
    }


def filter_queries_by_trends(queries: list, trends_data: dict, threshold: float = 0.0) -> list:
    """
    Filters queries based on trends data exceeding the threshold.
    """
    return [q for q in queries if trends_data.get(q, 0) > threshold]

def serpapi_youtube_search(query: str, output_dir: str, api_key: str, num_results=10):
    """
    Performs a YouTube search using SerpAPI and saves the HTML output.
    Returns a list of video dictionaries.
    """
    url = "https://serpapi.com/search"
    # JSON request
    params_json = {
        "engine": "youtube",
        "search_query": query,
        "api_key": api_key,
        "num": num_results
    }
    r_json = requests.get(url, params=params_json)
    data_json = r_json.json()

    # Also fetch HTML version
    params_html = {
        "engine": "youtube",
        "search_query": query,
        "api_key": api_key,
        "num": num_results,
        "output": "html"
    }
    r_html = requests.get(url, params=params_html)

    # Build a timestamped filename in the same folder
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = query.replace(' ', '_')
    filename_html = os.path.join(output_dir, f"search_{safe_query}_{timestamp}.html")
    
    with open(filename_html, "w", encoding="utf-8") as f:
        f.write(r_html.text)

    # Parse JSON results
    results = []
    if "video_results" in data_json:
        for video in data_json["video_results"]:
            link = video.get("link", "")
            parsed_id = None
            if "watch?v=" in link:
                parsed_id = link.split("watch?v=")[-1].split("&")[0]

            length_str = video.get("length")  # e.g. '12:34'
            total_seconds = parse_video_length(length_str)

            results.append({
                "title": video.get("title"),
                "link": link,
                "video_id": video.get("video_id") or parsed_id,
                "channel": video.get("channel", {}).get("name"),
                "views": video.get("views"),
                "snippet": video.get("snippet"),
                "length_str": length_str,          # store raw string
                "parsed_length": total_seconds,    # store total seconds
            })
    return results

def serpapi_youtube_video(video_id: str, api_key: str):
    """
    Fetches detailed information about a YouTube video using SerpAPI.
    """
    url = "https://serpapi.com/search"
    params = {
        "engine": "youtube_video",
        "v": video_id,
        "api_key": api_key
    }
    r = requests.get(url, params=params)
    return r.json()

def parse_related_videos(data: dict) -> list:
    """
    Parses related videos from SerpAPI YouTube video response.
    """
    related_videos = data.get("related_videos", [])
    parsed_videos = []
    for vid in related_videos:
        link = vid.get("link", "")
        parsed_id = None
        if "watch?v=" in link:
            parsed_id = link.split("watch?v=")[-1].split("&")[0]

        length_str = vid.get("length")  # e.g. '1:40:54'
        total_seconds = parse_video_length(length_str)

        parsed_views_count = parse_view_count(vid.get("views"))

        parsed_videos.append({
            "title": vid.get("title"),
            "link": link,
            "video_id": vid.get("video_id") or parsed_id,
            "channel": vid.get("channel", {}).get("name"),
            "views": vid.get("views"),
            "snippet": vid.get("snippet"),
            "length_str": length_str,
            "parsed_length": total_seconds,
            "parsed_views": parsed_views_count,   # new field
        })
    return parsed_videos

import os
import sys
import time
from dotenv import load_dotenv
from analysis_helpers import parse_video_length, parse_view_count
from serpapi_helpers import serpapi_youtube_video, parse_related_videos
import pandas as pd



def fetch_and_parse_related(video_id: str, api_key: str):
    """
    Fetch and parse related videos for a single video_id using SerpAPI.
    """
    data = serpapi_youtube_video(video_id, api_key)
    parsed = parse_related_videos(data)
    return parsed

def main():
    # 1. Load environment variables from .env
    load_dotenv()
    SERP_API_KEY = os.getenv("SERP_API_KEY")
    if not SERP_API_KEY:
        raise ValueError("SERP_API_KEY not found. Make sure it's set in your .env file.")

    # 2. Prompt user for a block of video IDs and parse them
    print("Paste your YouTube video IDs (one per line) then press Ctrl+D (or Enter twice on some systems) to finish:")
    input_string = sys.stdin.read().strip()  # read multi-line input
    initial_video_ids = [line.strip() for line in input_string.splitlines() if line.strip()]

    # 3. Set how many levels (depth) to fetch
    depth = 1  # Adjust as needed

    visited_video_ids = set()
    all_parsed_videos = []

    current_level_ids = initial_video_ids
    for level in range(depth):
        print(f"\n=== Depth Level {level + 1} ===")
        next_level_ids = []

        for vid_id in current_level_ids:
            if vid_id in visited_video_ids:
                continue

            visited_video_ids.add(vid_id)

            # Fetch and parse related videos
            parsed_related = fetch_and_parse_related(vid_id, SERP_API_KEY)
            all_parsed_videos.extend(parsed_related)

            # Collect new IDs to dive deeper
            for video_data in parsed_related:
                rel_id = video_data.get("video_id")
                if rel_id and rel_id not in visited_video_ids:
                    next_level_ids.append(rel_id)

            # OPTIONAL: Sleep to avoid rate limits or exceed usage
            time.sleep(1)

        current_level_ids = next_level_ids

    # 4. Print a summary of the collected videos
    print(f"\nCollected a total of {len(all_parsed_videos)} related videos.")
    df = pd.DataFrame(all_parsed_videos)

    # Save to CSV
    df.to_csv("related_videos.csv", index=False)
    print("Saved results to related_videos.csv")

if __name__ == "__main__":
    main()

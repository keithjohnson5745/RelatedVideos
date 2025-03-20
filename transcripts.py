#!/usr/bin/env python3

import os
import re
from datetime import datetime

# Make sure to install youtube_transcript_api first:
# pip install youtube-transcript-api
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


def extract_video_id(url_or_id):
    """
    Extracts a video ID from a YouTube URL or returns the ID if it's already one.
    Supports typical watch?v=ID and youtu.be/ID formats.
    """
    # Common YouTube URL patterns
    # e.g.: https://www.youtube.com/watch?v=VIDEO_ID
    # e.g.: https://youtu.be/VIDEO_ID
    youtube_id_regex = r'(?:v=|/)([0-9A-Za-z_-]{11})'
    match = re.search(youtube_id_regex, url_or_id)
    if match:
        return match.group(1)
    else:
        # If there's no match, assume the string is already a video ID
        # but check if it matches the typical 11-character ID pattern
        if len(url_or_id) == 11 and re.match(r'[0-9A-Za-z_-]{11}', url_or_id):
            return url_or_id
        else:
            return None


def get_transcript_text(video_id):
    """
    Fetches the transcript for a given video ID.
    Returns the combined transcript text if found, otherwise None.
    """
    try:
        # This returns a list of {text, start, duration}
        transcript_info = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine all 'text' lines into one string
        transcript_text = "\n".join([x['text'] for x in transcript_info])
        return transcript_text
    except TranscriptsDisabled:
        print(f"[Warning] Transcripts are disabled for video ID: {video_id}")
        return None
    except NoTranscriptFound:
        print(f"[Warning] No transcript found for video ID: {video_id}")
        return None
    except Exception as e:
        print(f"[Error] An unexpected error occurred for video ID {video_id}: {e}")
        return None


def main():
    # Create a 'results' folder if it doesn't exist
    results_folder = 'results'
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)

    print("Paste your video IDs or URLs (one per line).")
    print("Press ENTER on a blank line when you're finished.\n")

    # Collect user input lines
    lines = []
    while True:
        line = input().strip()
        if not line:  # blank line => done
            break
        lines.append(line)

    # Process each line
    for url_or_id in lines:
        video_id = extract_video_id(url_or_id)
        if not video_id:
            print(f"[Skipping] Invalid input: {url_or_id}")
            continue

        transcript_text = get_transcript_text(video_id)
        if transcript_text:
            # Generate timestamp for output file
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Construct a filename with the video ID + timestamp
            filename = f"{video_id}_{timestamp_str}.txt"
            output_path = os.path.join(results_folder, filename)

            # Write transcript to file
            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.write(transcript_text)

            print(f"[Success] Transcript saved for video ID '{video_id}' -> {output_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import os
import re
import sys
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
    youtube_id_regex = (
        r'(?:v=|/)([0-9A-Za-z_-]{11})'
    )
    
    match = re.search(youtube_id_regex, url_or_id)
    if match:
        return match.group(1)
    else:
        # If there's no match, assume the string is already a video ID
        # but check if it matches the typical 11-character ID
        if len(url_or_id) == 11 and re.match(r'[0-9A-Za-z_-]{11}', url_or_id):
            return url_or_id
        else:
            # Return None if it's invalid
            return None

def get_transcript_text(video_id):
    """
    Fetches the transcript for a given video ID.
    Returns the combined transcript text if found.
    """
    try:
        # This returns a list of {text, start, duration}
        transcript_info = YouTubeTranscriptApi.get_transcript(video_id)
        # Combine all 'text' into one block, or handle as needed
        transcript_text = "\n".join([x['text'] for x in transcript_info])
        return transcript_text
    except TranscriptsDisabled:
        print(f"Transcripts are disabled for video ID: {video_id}")
        return None
    except NoTranscriptFound:
        print(f"No transcript found for video ID: {video_id}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred for video ID {video_id}: {e}")
        return None

def main(video_list_file):
    # Create a 'results' folder if it doesn't exist
    results_folder = 'results'
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)

    # Read lines from the file
    with open(video_list_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    for url_or_id in lines:
        video_id = extract_video_id(url_or_id)
        if not video_id:
            print(f"Skipping invalid input: {url_or_id}")
            continue
        
        transcript_text = get_transcript_text(video_id)
        if transcript_text:
            # Generate timestamp for output file
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Construct a filename with the video ID and the current timestamp
            filename = f"{video_id}_{timestamp_str}.txt"
            output_path = os.path.join(results_folder, filename)

            # Write to the output file
            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.write(transcript_text)
            
            print(f"Transcript saved for video ID '{video_id}' to {output_path}")

if __name__ == "__main__":
    """
    Usage:
      python get_youtube_transcripts.py video_list.txt
      
    Where 'video_list.txt' contains one video ID or YouTube URL per line.
    """
    if len(sys.argv) < 2:
        print("Usage: python get_youtube_transcripts.py <video_list_file>")
        sys.exit(1)

    video_list_file = sys.argv[1]
    main(video_list_file)

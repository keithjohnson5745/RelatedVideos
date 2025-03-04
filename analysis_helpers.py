
# utils/analysis_helpers.py
import re
import math
from collections import Counter, defaultdict

def parse_view_count(views):
    if isinstance(views, int):
        return views
    elif isinstance(views, str):
        digits = "".join(filter(str.isdigit, views))
        if digits:
            return int(digits)
    return 0

def analyze_channels(videos):
    channel_dict = {}
    for v in videos:
        ch = v.get("channel_name") or v.get("channel") or "UnknownChannel"
        if ch not in channel_dict:
            channel_dict[ch] = {"count": 0, "views": 0, "videos": []}
        channel_dict[ch]["count"] += 1
        channel_dict[ch]["views"] += parse_view_count(v.get("views"))
        channel_dict[ch]["videos"].append(v.get("title", ""))
    return channel_dict

def parse_video_length(length_str: str) -> int:
    if not length_str or not isinstance(length_str, str):
        return 0

    parts = length_str.split(":")
    parts = [p.strip() for p in parts]
    try:
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            total_seconds = minutes * 60 + seconds
        elif len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            total_seconds = hours * 3600 + minutes * 60 + seconds
        else:
            total_seconds = 0
    except ValueError:
        total_seconds = 0

    return total_seconds

def log_transform(x):
    return math.log10(x + 1)

def ngramize(tokens, n=1):
    """
    Given a list of tokens, produce an n-gram list.
    """
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def analyze_titles_for_themes(videos):
    all_titles = [v.get("title", "") for v in videos]
    token_pattern = re.compile(r"\w+")
    all_unigrams = []
    for title in all_titles:
        tokens = token_pattern.findall(title.lower())
        all_unigrams.extend(tokens)

    stop_words = set([
        "the","and","of","a","to","in","for","i","we","you","my",
        "on","it","is","do","this","with","that","at","up","by",
        "what","if","how","from","1","2","3","4","5","6","7","8","9","0"
    ])
    unigrams_filtered = [t for t in all_unigrams if t not in stop_words]

    # Unigram freq
    uni_counter = Counter(unigrams_filtered)
    unigrams_most_common = uni_counter.most_common(20)

    # Bigrams
    all_bigrams = []
    for i in range(len(unigrams_filtered)-1):
        bigram = unigrams_filtered[i] + " " + unigrams_filtered[i+1]
        all_bigrams.append(bigram)
    bi_counter = Counter(all_bigrams)
    bigrams_most_common = bi_counter.most_common(20)

    # Trigrams
    all_trigrams = []
    for i in range(len(unigrams_filtered)-2):
        trigram = unigrams_filtered[i] + " " + unigrams_filtered[i+1] + " " + unigrams_filtered[i+2]
        all_trigrams.append(trigram)
    tri_counter = Counter(all_trigrams)
    trigrams_most_common = tri_counter.most_common(20)

    return {
        "unigrams": unigrams_most_common,
        "bigrams": bigrams_most_common,
        "trigrams": trigrams_most_common
    }

def categorize_videos_by_length(videos):
    bins = {
        "0-1 min": 0,
        "1-5 min": 0,
        "5-10 min": 0,
        "10-20 min": 0,
        "20+ min": 0
    }

    for vid in videos:
        seconds = vid.get("parsed_length", 0)
        if seconds <= 60:
            bins["0-1 min"] += 1
        elif seconds < 300:   # 5 min
            bins["1-5 min"] += 1
        elif seconds < 600:   # 10 min
            bins["5-10 min"] += 1
        elif seconds < 1200:  # 20 min
            bins["10-20 min"] += 1
        else:
            bins["20+ min"] += 1

    return bins

def categorize_videos_by_views(videos, view_bands=None):
    if view_bands is None:
        view_bands = [
            (0, 5000),
            (5000, 20000),
            (20000, 50000),
            (50000, 100000),
            (100000, 500000),
            (500000, 1000000),
            (1000000, None)  # "more than 1,000,000"
        ]

    unique_ids = set()
    deduped = []
    for vid in videos:
        vid_id = vid.get("video_id")
        if vid_id not in unique_ids:
            unique_ids.add(vid_id)
            deduped.append(vid)

    band_counts = {}
    for (low, high) in view_bands:
        if high is None:
            label = f"{low}+"
        else:
            label = f"{low}-{high}"
        band_counts[label] = 0

    for vid in deduped:
        vcount = vid.get("parsed_views", 0)
        placed = False
        for (low, high) in view_bands:
            if high is None:
                if vcount >= low:
                    label = f"{low}+"
                    band_counts[label] += 1
                    placed = True
                    break
            else:
                if low <= vcount < high:
                    label = f"{low}-{high}"
                    band_counts[label] += 1
                    placed = True
                    break
        if not placed:
            pass  # Optionally handle 'unknown' or 'out of range'

    return band_counts


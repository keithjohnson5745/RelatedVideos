import os
import sys
import time
import requests
import pandas as pd

from dotenv import load_dotenv  # For environment variable loading
import networkx as nx
import community  # from the "python-louvain" package
from pyvis.network import Network

###############################################################################
# 1. HELPER FUNCTIONS (Embedded from analysis_helpers.py & serpapi_helpers.py)
###############################################################################

def parse_video_length(length_str: str) -> int:
    """
    Converts a time string like "12:34" or "1:02:45" into total seconds.
    """
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


def parse_view_count(views):
    """
    Convert a string like "12K views" or "3,456" to an integer.
    """
    if isinstance(views, int):
        return views
    elif isinstance(views, str):
        # Remove all non-digit chars
        digits = "".join(filter(str.isdigit, views))
        if digits:
            return int(digits)
    return 0


def serpapi_youtube_video(video_id: str, api_key: str):
    """
    Fetch detailed information about a YouTube video using SerpAPI.
    Returns the JSON response (including 'related_videos').
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
    Parses the 'related_videos' section from a SerpAPI YouTube video response.
    Returns a list of dicts with fields:
       "video_id", "title", "channel", "views", "parsed_length", "parsed_views", ...
    """
    related_videos = data.get("related_videos", [])
    parsed_videos = []
    for vid in related_videos:
        link = vid.get("link", "")
        parsed_id = None
        if "watch?v=" in link:
            parsed_id = link.split("watch?v=")[-1].split("&")[0]

        length_str = vid.get("length", "")  # e.g. '1:40:54'
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
            "parsed_views": parsed_views_count,
        })
    return parsed_videos

###############################################################################
# 2. NETWORK-BUILDING & ANALYSIS FUNCTIONS
###############################################################################

def build_and_analyze_graph(search_videos, related_videos):
    """
    1. Build a directed NetworkX graph from (search + related).
    2. Compute centralities, 'influence', and community detection.
    Returns the resulting DiGraph.
    """
    G = nx.DiGraph()

    # Add "search" videos as nodes (optional distinction)
    for vid in search_videos:
        vid_id = vid.get("video_id")
        if vid_id:
            G.add_node(vid_id,
                       title=vid.get("title",""),
                       channel=vid.get("channel",""),
                       views=parse_view_count(vid.get("views")),
                       parsed_length=vid.get("parsed_length", 0))

    # Add "related" as nodes + edges
    for rel in related_videos:
        child_vid = rel.get("video_id")
        parent_vid = rel.get("related_to")
        if child_vid and parent_vid:
            if child_vid not in G.nodes:
                G.add_node(child_vid,
                           title=rel.get("title",""),
                           channel=rel.get("channel",""),
                           views=parse_view_count(rel.get("views")),
                           parsed_length=rel.get("parsed_length", 0))
            G.add_edge(parent_vid, child_vid)

    # ---- Compute centralities ----
    in_degree_cent = nx.in_degree_centrality(G)
    betweenness = nx.betweenness_centrality(G)
    eigenvector = nx.eigenvector_centrality(G, max_iter=1000)
    pagerank = nx.pagerank(G)

    # Assign them to node data
    for node in G.nodes():
        G.nodes[node]["in_degree_cent"] = in_degree_cent.get(node, 0.0)
        G.nodes[node]["betweenness"] = betweenness.get(node, 0.0)
        G.nodes[node]["eigenvector"] = eigenvector.get(node, 0.0)
        G.nodes[node]["pagerank"] = pagerank.get(node, 0.0)
        # Weighted influence
        G.nodes[node]["influence"] = (
            0.4 * G.nodes[node]["in_degree_cent"] +
            0.3 * G.nodes[node]["betweenness"] +
            0.2 * G.nodes[node]["eigenvector"] +
            0.1 * G.nodes[node]["pagerank"]
        )

    # ---- Community detection (Louvain) ----
    undirected = G.to_undirected()
    partition = community.best_partition(undirected)
    for node, comm_id in partition.items():
        G.nodes[node]["community"] = comm_id

    return G


def export_network_html(G, output_html="video_network.html"):
    """
    Build a PyVis interactive HTML network graph, scaled by 'influence' and
    colored by 'community'.
    """
    net = Network(height="800px", width="1200px", directed=True, notebook=False, cdn_resources='remote')
    net.force_atlas_2based()
    net.show_buttons(filter_=['nodes', 'edges', 'physics', 'layout'])

    # Range of influence for node-size scaling
    influences = [G.nodes[n].get("influence", 0) for n in G.nodes]
    if influences:
        inf_min, inf_max = min(influences), max(influences)
    else:
        inf_min, inf_max = 0, 1

    # We'll just generate random colors for each community
    import random
    community_colors = {}
    for node in G.nodes():
        comm_id = G.nodes[node].get("community", 0)
        if comm_id not in community_colors:
            color = f"#{random.randint(0, 0xFFFFFF):06x}"
            community_colors[comm_id] = color

    # Add nodes
    for node in G.nodes():
        data = G.nodes[node]
        influence = data.get("influence", 0)
        comm_id   = data.get("community", 0)
        if inf_max != inf_min:
            size = 5 + 35*(influence - inf_min)/(inf_max - inf_min)
        else:
            size = 10

        label_text = (
            f"Title: {data.get('title','')}\n"
            f"Channel: {data.get('channel','')}\n"
            f"Views: {data.get('views',0)}\n"
            f"Influence: {influence:.4f}\n"
            f"Community: {comm_id}"
        )
        net.add_node(
            node,
            label=label_text,
            title=label_text,
            size=size,
            color=community_colors.get(comm_id, "#999999")
        )

    # Add edges
    for src, dst in G.edges():
        net.add_edge(src, dst, value=1, title="related")

    net.write_html(output_html)
    print(f"Created PyVis graph: {output_html}")


def export_advanced_stats_to_csv(G, output_csv="network_advanced_stats.csv"):
    """
    Write each node's advanced stats to a CSV:
      video_id, title, channel, views, in_degree_cent, betweenness,
      eigenvector, pagerank, influence, community
    """
    rows = []
    for node, data in G.nodes(data=True):
        row = {
            "video_id": node,
            "title": data.get("title",""),
            "channel": data.get("channel",""),
            "views": data.get("views",0),
            "in_degree_cent": data.get("in_degree_cent",0.0),
            "betweenness": data.get("betweenness",0.0),
            "eigenvector": data.get("eigenvector",0.0),
            "pagerank": data.get("pagerank",0.0),
            "influence": data.get("influence",0.0),
            "community": data.get("community",0),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    print(f"Exported advanced stats to {output_csv}")


###############################################################################
# 3. MAIN SCRIPT
###############################################################################

def main():
    # Load environment (expect SERP_API_KEY in .env)
    load_dotenv()
    serp_api_key = os.getenv("SERP_API_KEY")
    if not serp_api_key:
        raise ValueError("SERP_API_KEY not found. Please set it in your .env file.")

    # Create results directory if needed
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)

    # Prompt for prefix
    prefix = input("Enter a prefix for output files (e.g., 'myproject'): ").strip()
    if not prefix:
        prefix = "output"  # default fallback

    # Prompt for depth at the start
    depth_str = input("Enter the depth for searching related videos (default = 1): ").strip()
    try:
        depth = int(depth_str)
    except ValueError:
        depth = 1
    if depth < 1:
        depth = 1

    ########################################################################
    # Ask if user wants to skip data collection
    ########################################################################
    skip_collection = input("Skip data collection and build network from existing CSV? (yes/no) ").strip().lower()
    if skip_collection in ("yes", "y"):
        # Prompt for path to the CSV
        csv_path = input("Enter the path to your related_videos.csv: ").strip()
        if not os.path.isfile(csv_path):
            print(f"Error: File not found at '{csv_path}'. Cannot skip data collection.")
            print("Returning to normal data collection flow...\n")
            skip_collection = "no"  # fallback to normal flow
        else:
            # We have a valid CSV path
            df = pd.read_csv(csv_path)
            # Ask if we should create the network graph
            choice = input("Would you like to create a network graph now? (yes/no) ").lower().strip()
            if choice in ("yes", "y"):
                # Build the graph from the existing CSV
                df_search = df[df["related_to"].isna()].copy()
                df_related = df[~df["related_to"].isna()].copy()

                search_list = df_search.to_dict(orient="records")
                related_list = df_related.to_dict(orient="records")

                G = build_and_analyze_graph(search_list, related_list)

                # Name outputs with your chosen prefix
                html_path = os.path.join(results_dir, f"{prefix}_video_network.html")
                csv_stats_path = os.path.join(results_dir, f"{prefix}_network_advanced_stats.csv")

                export_network_html(G, html_path)
                export_advanced_stats_to_csv(G, csv_stats_path)

                print("\nAll done! Check your results folder for outputs.")
            else:
                print("No network graph created. Exiting.")
            return  # End the script here

    ########################################################################
    # If NOT skipping (or skip failed), do the normal data-collection flow
    ########################################################################

    # 1. Prompt for initial video IDs
    print("Paste your YouTube video IDs (one per line), then press Ctrl+D (or Enter twice) to finish:")
    input_string = sys.stdin.read().strip()
    initial_video_ids = [line.strip() for line in input_string.splitlines() if line.strip()]

    visited_video_ids = set()
    all_parsed_videos = []

    current_level_ids = initial_video_ids
    for level in range(depth):
        print(f"\n=== Depth Level {level+1} ===")
        next_level_ids = []

        for vid_id in current_level_ids:
            if vid_id in visited_video_ids:
                continue
            visited_video_ids.add(vid_id)

            # Fetch details for this video from SerpAPI
            data = serpapi_youtube_video(vid_id, serp_api_key)
            parsed_related = parse_related_videos(data)

            # Mark each related video with "related_to" = the current video
            for item in parsed_related:
                item["related_to"] = vid_id

            all_parsed_videos.extend(parsed_related)

            # Collect new IDs for next level
            for video_data in parsed_related:
                rel_id = video_data.get("video_id")
                if rel_id and rel_id not in visited_video_ids:
                    next_level_ids.append(rel_id)

            # Sleep a bit to avoid rate-limits
            time.sleep(1)

        current_level_ids = next_level_ids

    # 3. Save to CSV with prefix in results folder
    csv_output_path = os.path.join(results_dir, f"{prefix}_related_videos.csv")
    df = pd.DataFrame(all_parsed_videos)
    df.to_csv(csv_output_path, index=False)
    print(f"Collected {len(all_parsed_videos)} related videos.")
    print(f"Saved to '{csv_output_path}'.")

    # 4. Ask if user wants to create a network graph
    choice = input("Would you like to create a network graph? (yes/no) ").lower().strip()
    if choice not in ("yes", "y"):
        print("Skipping network creation. Done!")
        return

    # 5. Build the graph
    df_search = df[df["related_to"].isna()].copy()
    df_related = df[~df["related_to"].isna()].copy()

    search_list = df_search.to_dict(orient="records")
    related_list = df_related.to_dict(orient="records")

    G = build_and_analyze_graph(search_list, related_list)

    # 6. Export PyVis HTML & advanced stats CSV, with prefix
    html_path = os.path.join(results_dir, f"{prefix}_video_network.html")
    csv_stats_path = os.path.join(results_dir, f"{prefix}_network_advanced_stats.csv")

    export_network_html(G, html_path)
    export_advanced_stats_to_csv(G, csv_stats_path)

    print("\nAll done! Check your 'results' folder for outputs:")
    print(f"  - {html_path}\n  - {csv_stats_path}\n")


if __name__ == "__main__":
    main()

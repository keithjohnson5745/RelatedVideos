# **YouTube Related-Video Collector & Network Analyzer**

This script automates the process of:

1. Fetching related YouTube videos via [SerpAPI](https://serpapi.com/).
2. Storing their metadata in CSV format.
3. Optionally building a **directed network graph** (with PyVis + NetworkX) to visualize and analyze relationships (related-to edges).
4. Saving advanced centrality measures and community assignments for each video to a CSV.

## **Features**

- **Prefix-Based Output**: At runtime, you choose a prefix (e.g. myproject) which is prepended to all output files (e.g. myproject_related_videos.csv, myproject_video_network.html, etc.).
- **Configurable Depth**: Specify how many “hops” (levels) of related videos to explore.
- **Skipping Data Collection**: If you already have a related_videos.csv, you can skip SerpAPI fetching and go straight to building / analyzing the network from your existing CSV file.
- **NetworkX Analysis**:
  - Calculates in_degree_centrality, betweenness_centrality, eigenvector_centrality, and pagerank.
  - Combines these metrics into a single “influence” score.
  - Performs **Louvain community detection** (via python-louvain).
- **Interactive Network Visualization**: Creates a PyVis HTML file with node sizes scaled by influence, color-coded by community.
- **All Outputs Saved in a results/ Folder**: Ensures your project stays organized.

## **Requirements**

1. **Python 3.7+** (recommended).
2. The following Python libraries:
    - requests
    - python-dotenv
    - networkx
    - python-louvain (installed as community in Python)
    - pyvis
3. A **SerpAPI** account, with a valid **API key**.

You can install the required libraries using:

bash

CopyEdit

pip install requests python-dotenv networkx python-louvain pyvis

## **Setup**

1. **Clone or copy** this script into your project folder (e.g. youtube_network.py).

**Create a .env file** in the same folder with the line:  
ini  
CopyEdit  
SERP_API_KEY=YOUR_KEY_HERE

1. or set SERP_API_KEY as an environment variable in your system.
2. **Create** a results/ subfolder (though the script will do this automatically if it doesn’t exist).

## **Usage**

Run the script:

bash

CopyEdit

python youtube_network.py

You’ll be prompted for:

1. **Prefix for output files  
    **E.g. myproject → will produce files named myproject_related_videos.csv, myproject_video_network.html, myproject_network_advanced_stats.csv, etc.
2. **Depth  
    **How many “hops” (levels) of related videos to follow. A depth of 1 means “initial video IDs + their immediate related videos.” A depth of 2 goes further, pulling related videos of the _related videos,_ and so on.
3. **Skip data collection?**
    - If you type “yes,” it will ask for the path to an existing CSV file.
    - Then it will optionally build the network from that CSV.
    - This is **useful** if you already have the data or don’t want to re-fetch from SerpAPI.
4. If **not skipping**, the script will prompt you to **paste** your YouTube video IDs (one per line). End with **Ctrl+D** (Unix/Mac) or **Enter** + **Ctrl+Z** (Windows), depending on your terminal.
5. After collecting data (if you didn’t skip), it will ask if you want to **create a network graph**. If you say yes, it builds the PyVis HTML network and outputs an advanced stats CSV.

### **Example Flow**

**Run**:  
bash  
CopyEdit  
python youtube_network.py

1. **Prefix**: myproject
2. **Depth**: 2
3. **Skip collection?**: no

(Script prompts) _Paste your YouTube video IDs._ For example:  
nginx  
CopyEdit  
xYzAbC123

dQw4w9WgXcQ

1. Press Ctrl+D (or equivalent) to finish.
2. The script fetches data from SerpAPI, saves results/myproject_related_videos.csv.
3. It asks if you want to build a network. If **yes**, you’ll get:
    - results/myproject_video_network.html (interactive PyVis view)
    - results/myproject_network_advanced_stats.csv (centralities, influence, and communities for each node)

### **Outputs**

- **\[prefix\]\_related_videos.csv**: Each row is one “related video,” including video_id, channel, parsed_length, parsed_views, plus a related_to indicating the parent video.
- **\[prefix\]\_video_network.html**: A PyVis HTML that visualizes the network.
- **\[prefix\]\_network_advanced_stats.csv**: Each row represents a single video (node) with columns for centralities, an “influence” score, and a “community” label.

## **Notes and Tips**

- If you set **depth** > 1, the script can collect a large number of videos (since each wave of related videos spawns more IDs).
- To avoid SerpAPI rate limits, the script sleeps 1 second after each video’s data fetch.

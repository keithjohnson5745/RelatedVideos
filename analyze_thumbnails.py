import csv
import json
import os
import requests
from dotenv import load_dotenv
from io import BytesIO
from openai import OpenAI
from colorthief import ColorThief
from datetime import datetime

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

def load_video_ids_from_csv(file_path):
    """
    Reads a file line-by-line and returns a list of YouTube video IDs.
    Assumes one video ID per line.
    """
    video_ids = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:  # Skip empty lines
                video_ids.append(line)
    return video_ids

def generate_youtube_thumbnail_urls(video_ids):
    base_url = "http://img.youtube.com/vi"
    return [f"{base_url}/{vid}/maxresdefault.jpg" for vid in video_ids]

def extract_colors_from_url(url, color_count=3):
    response = requests.get(url)
    response.raise_for_status()
    img_bytes = BytesIO(response.content)
    color_thief = ColorThief(img_bytes)
    palette_rgb = color_thief.get_palette(color_count=color_count)
    hex_palette = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in palette_rgb]
    return hex_palette

def analyze_image_with_gpt(image_url, color_palette_hex):
    system_message = {
        "role": "system",
        "content": (
            "You are a JSON output generator. You respond to user requests ONLY "
            "with valid JSON. No markdown, no code fences, no additional commentary."
        )
    }

    # text_style_category => [BOLD, REGULAR, SCRIPT, MODERN, CLASSIC, FUNKY, OTHER]
    # color_category_strict => [warm, cool, neutral, pastel, bright, dark, other]
    # faces_emotions_only => array of strings (just the emotion words)
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "Analyze this YouTube thumbnail. Return VALID JSON ONLY with the fields:\n"
                    "```\n"
                    "{\n"
                    "  \"detected_text\": \"string\",\n"
                    "  \"objects\": [\"string\"],\n"
                    "  \"people_count\": integer,\n"
                    "  \"faces\": [\n"
                    "    {\n"
                    "      \"emotion\": \"string\",\n"
                    "      \"description\": \"string\"\n"
                    "    }\n"
                    "  ],\n"
                    "  \"brand_logos\": [\"string\"],\n"
                    "  \"layout\": \"string\",\n"
                    "  \"font_style\": \"string\",\n"
                    "  \"cta_detected\": boolean,\n"
                    "  \"scene_classification\": \"string\",\n"
                    "  \"color_scheme\": \"string\",\n"
                    "  \"summary\": \"string\",\n"
                    "  \"faces_emotions_only\": [\"string\"],\n"
                    "  \"text_style_category\": \"string\",  # One of [BOLD, REGULAR, SCRIPT, MODERN, CLASSIC, FUNKY, OTHER]\n"
                    "  \"color_category_strict\": \"string\"  # One of [warm, cool, neutral, pastel, bright, dark, other]\n"
                    "}\n"
                    "```\n"
                    "\n"
                    "Rules:\n"
                    "- If multiple faces, add each face's `emotion` to `faces_emotions_only`.\n"
                    "- For `text_style_category`, pick the single best match from [BOLD, REGULAR, SCRIPT, MODERN, CLASSIC, FUNKY, OTHER].\n"
                    "- For `color_category_strict`, pick the single best match from [warm, cool, neutral, pastel, bright, dark, other].\n"
                    "- No extra text outside the JSON object.\n\n"
                    f"Local color palette (hex): {', '.join(color_palette_hex)}\n"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            },
        ]
    }

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[system_message, user_message]
    )
    return response.choices[0].message.content

def parse_gpt_json(raw_analysis, do_repair_pass=True):
    start_idx = raw_analysis.find('{')
    end_idx = raw_analysis.rfind('}')
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        json_candidate = raw_analysis[start_idx : end_idx + 1]
        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass  # We'll try the repair pass next

    # Repair pass: second GPT attempt if desired
    if do_repair_pass:
        global client
        repair_prompt = (
            "Convert the following text into valid JSON only, with no extra text:\n"
            f"{raw_analysis}"
        )
        try:
            repair_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": repair_prompt}]
            )
            repaired_text = repair_response.choices[0].message.content
            rs_start = repaired_text.find('{')
            rs_end = repaired_text.rfind('}')
            if rs_start != -1 and rs_end != -1 and rs_start < rs_end:
                repaired_candidate = repaired_text[rs_start : rs_end + 1]
                try:
                    return json.loads(repaired_candidate)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    return {}

def batch_analyze_thumbnails(video_ids, output_csv):
    fieldnames = [
        "video_id",
        "thumbnail_url",
        "color_palette_hex",
        "detected_text",
        "objects",
        "people_count",
        "faces",
        "brand_logos",
        "layout",
        "font_style",
        "cta_detected",
        "scene_classification",
        "color_scheme",
        "summary",
        "faces_emotions_only",
        "text_style_category",
        "color_category_strict",
        "raw_analysis"
    ]

    thumbnail_urls = generate_youtube_thumbnail_urls(video_ids)

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for vid, url in zip(video_ids, thumbnail_urls):
            row_data = {
                "video_id": vid,
                "thumbnail_url": url,
                "color_palette_hex": "",
                "detected_text": "",
                "objects": "",
                "people_count": "",
                "faces": "",
                "brand_logos": "",
                "layout": "",
                "font_style": "",
                "cta_detected": "",
                "scene_classification": "",
                "color_scheme": "",
                "summary": "",
                "faces_emotions_only": "",
                "text_style_category": "",
                "color_category_strict": "",
                "raw_analysis": ""
            }

            try:
                # Extract local color data
                hex_palette = extract_colors_from_url(url, color_count=3)
                row_data["color_palette_hex"] = ", ".join(hex_palette)

                # GPT analysis
                raw_analysis = analyze_image_with_gpt(url, hex_palette)
                row_data["raw_analysis"] = raw_analysis

                # Parse JSON
                parsed = parse_gpt_json(raw_analysis, do_repair_pass=True)

                # Fill out fields
                row_data["detected_text"] = parsed.get("detected_text", "")
                row_data["objects"] = ", ".join(parsed.get("objects", []))
                row_data["people_count"] = str(parsed.get("people_count", ""))

                faces = parsed.get("faces", [])
                row_data["faces"] = "; ".join(
                    f"{face.get('emotion','?')}({face.get('description','')})"
                    for face in faces
                )

                row_data["brand_logos"] = ", ".join(parsed.get("brand_logos", []))
                row_data["layout"] = parsed.get("layout", "")
                row_data["font_style"] = parsed.get("font_style", "")
                row_data["cta_detected"] = str(parsed.get("cta_detected", ""))
                row_data["scene_classification"] = parsed.get("scene_classification", "")
                row_data["color_scheme"] = parsed.get("color_scheme", "")
                row_data["summary"] = parsed.get("summary", "")

                raw_faces_emotions = parsed.get("faces_emotions_only", [])
                if isinstance(raw_faces_emotions, list):
                    row_data["faces_emotions_only"] = ", ".join(raw_faces_emotions)
                else:
                    row_data["faces_emotions_only"] = str(raw_faces_emotions)

                row_data["text_style_category"] = parsed.get("text_style_category", "")
                row_data["color_category_strict"] = parsed.get("color_category_strict", "")

            except Exception as e:
                row_data["summary"] = f"Error: {str(e)}"

            writer.writerow(row_data)

    print(f"Analysis complete! Results stored in '{output_csv}'.")


if __name__ == "__main__":
    # 1) Load video IDs from a file (each line is an ID, no quotes needed).
    video_ids_file = "/Users/keithjohnson/Desktop/RelatedVideos/CSVs to load/videolist_LATRYGUY_2025_03_19-18_25_42 video IDs.csv"  # <--- Update this to your file
    video_ids = load_video_ids_from_csv(video_ids_file)

    # 2) Create an output filename with today's date
    today_str = datetime.now().strftime("%Y%m%d")
    output_filename = f"results/youtube_thumbnail_analysis_extended_{today_str}.csv"

    # 3) Run the batch analysis
    batch_analyze_thumbnails(video_ids, output_csv=output_filename)
    print("Done.")
# This script analyzes YouTube thumbnails by extracting color palettes and using GPT for analysis.
# It loads video IDs from a CSV file, generates thumbnail URLs, extracts colors,
# and performs a detailed analysis using GPT, storing the results in a CSV file.

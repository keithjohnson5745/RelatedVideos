import csv
import json
import os
import requests
from dotenv import load_dotenv
from io import BytesIO
from openai import OpenAI
from colorthief import ColorThief

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize the OpenAI client
client = OpenAI(api_key=openai_api_key)

# ---------------------------------------------
# Generate YouTube Thumbnail URLs
# ---------------------------------------------
def generate_youtube_thumbnail_urls(video_ids):
    """
    Given a list of YouTube video IDs, returns a list of
    maxresdefault thumbnail URLs.
    """
    base_url = "http://img.youtube.com/vi"
    return [f"{base_url}/{vid}/maxresdefault.jpg" for vid in video_ids]


# ---------------------------------------------
# Local Color Extraction (colorthief)
# ---------------------------------------------
def extract_colors_from_url(url, color_count=3):
    """
    Downloads the thumbnail from 'url', then uses colorthief
    to find the top 'color_count' dominant colors.
    Returns a list of hex codes, e.g. ['#ff0000','#00ff00','#0000ff'].
    """
    response = requests.get(url)
    response.raise_for_status()
    img_bytes = BytesIO(response.content)

    color_thief = ColorThief(img_bytes)
    palette_rgb = color_thief.get_palette(color_count=color_count)

    # Convert each (r,g,b) to a hex string
    hex_palette = [f"#{r:02x}{g:02x}{b:02x}" for (r, g, b) in palette_rgb]
    return hex_palette


# ---------------------------------------------
# GPT-based Thumbnail Analysis with JSON Focus
# ---------------------------------------------
def analyze_image_with_gpt(image_url, color_palette_hex):
    """
    Calls GPT to analyze the thumbnail (via image URL), plus interpret
    the local color palette (color_palette_hex). Returns raw textual
    output from GPT, which we will attempt to parse.
    """

    # 1) We add a SYSTEM message emphasizing strict JSON output
    system_message = {
        "role": "system",
        "content": (
            "You are a JSON output generator. You respond to user requests ONLY "
            "with valid JSON. No markdown, no code fences, no additional commentary. "
            "If you include any explanation, do so strictly as valid JSON fields."
        )
    }

    # 2) Our user prompt describes the fields we want
    #    and provides local color data plus the image URL.
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    "Analyze this YouTube thumbnail. Return VALID JSON ONLY with these fields:\n"
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
                    "  \"text_style\": \"string\",\n"
                    "  \"cta_detected\": boolean,\n"
                    "  \"scene_classification\": \"string\",\n"
                    "  \"color_scheme\": \"string\",\n"
                    "  \"color_category\": \"string\",\n"
                    "  \"summary\": \"string\"\n"
                    "}\n"
                    "```\n"
                    "NO extra text outside that JSON. No code fences. \n\n"
                    f"Local color palette (hex): {', '.join(color_palette_hex)}\n"
                )
            },
            {
                "type": "image_url",
                "image_url": {"url": image_url},
            },
        ]
    }

    # 3) Make the call
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[system_message, user_message]
    )

    # 4) Return GPT's raw response (we will parse it later)
    return response.choices[0].message.content


def parse_gpt_json(raw_analysis, do_repair_pass=True):
    """
    Attempts to parse 'raw_analysis' as JSON using:
     1) Substring extraction (from first '{' to last '}')
     2) If needed, a GPT repair pass
    Returns a Python dict (parsed JSON) or empty dict if all fails.
    """

    # ------------------------------------
    # A) Substring Extraction
    # ------------------------------------
    start_idx = raw_analysis.find('{')
    end_idx = raw_analysis.rfind('}')
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        json_candidate = raw_analysis[start_idx : end_idx + 1]

        try:
            return json.loads(json_candidate)
        except json.JSONDecodeError:
            pass  # We'll try the repair pass next

    # ------------------------------------
    # B) Repair Pass (if enabled)
    # ------------------------------------
    if do_repair_pass:
        # We'll do a second GPT call to fix the text
        # But we need an API client again. (We can reuse the global client.)
        from openai import OpenAI
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

            # Try substring extraction on the repaired text
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

    # If we reach here, no valid JSON could be parsed
    return {}


# ---------------------------------------------
# 5) Batch Analysis
# ---------------------------------------------
def batch_analyze_thumbnails(video_ids, output_csv="thumbnail_analysis_extended.csv"):
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
        "text_style",
        "cta_detected",
        "scene_classification",
        "color_scheme",
        "color_category",
        "summary",
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
                "text_style": "",
                "cta_detected": "",
                "scene_classification": "",
                "color_scheme": "",
                "color_category": "",
                "summary": "",
                "raw_analysis": ""
            }

            try:
                # 1) Extract local color data (top 3 hex)
                hex_palette = extract_colors_from_url(url, color_count=3)
                row_data["color_palette_hex"] = ", ".join(hex_palette)

                # 2) Call GPT
                raw_analysis = analyze_image_with_gpt(url, hex_palette)
                row_data["raw_analysis"] = raw_analysis  # store for reference

                # 3) Attempt to parse
                parsed = parse_gpt_json(raw_analysis, do_repair_pass=True)

                # 4) Fill out fields from parsed data
                row_data["detected_text"] = parsed.get("detected_text", "")
                row_data["objects"] = ", ".join(parsed.get("objects", []))
                row_data["people_count"] = str(parsed.get("people_count", ""))

                # For faces, store as a semicolon-delimited string
                faces = parsed.get("faces", [])
                row_data["faces"] = "; ".join(
                    f"{face.get('emotion','?')}({face.get('description','')})"
                    for face in faces
                )

                row_data["brand_logos"] = ", ".join(parsed.get("brand_logos", []))
                row_data["layout"] = parsed.get("layout", "")
                row_data["text_style"] = parsed.get("text_style", "")
                row_data["cta_detected"] = str(parsed.get("cta_detected", ""))
                row_data["scene_classification"] = parsed.get("scene_classification", "")
                row_data["color_scheme"] = parsed.get("color_scheme", "")
                row_data["color_category"] = parsed.get("color_category", "")
                row_data["summary"] = parsed.get("summary", "")

                # If 'parsed' was empty or incomplete, you can handle that here,
                # e.g. if row_data["detected_text"] is empty => GPT didn't parse well.

            except Exception as e:
                row_data["summary"] = f"Error: {str(e)}"

            writer.writerow(row_data)

    print(f"Analysis complete! Results stored in '{output_csv}'.")


# ---------------------------------------------
# Example Usage
# ---------------------------------------------
if __name__ == "__main__":
    # Provide a list of YouTube video IDs
    video_ids = [
        "gPhar6Qpkts",
        "XySzDtCHn6A"
    ]

    batch_analyze_thumbnails(
        video_ids,
        output_csv="results/youtube_thumbnail_analysis_extended.csv"
    )
    print("Done.")

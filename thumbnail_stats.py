#!/usr/bin/env python3

import os
import re
import base64
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO, StringIO
from collections import Counter
from itertools import islice
from dotenv import load_dotenv

# pip install openai
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

###############################################################################
# Minimal English stopwords set. For advanced usage, consider nltk or spaCy.  #
###############################################################################
STOPWORDS = {
    "the", "and", "a", "to", "of", "in", "for", "on", "with", "at", "by",
    "an", "be", "this", "that", "it", "from", "as", "or", "up", "is", "are",
    "was", "were", "so", "if", "out", "too", "any", "can", "but", "not",
    "off", "into", "we", "you", "your", "i", "our", "they", "their", "them",
    "her", "his", "he", "she", "hers", "him", "its", "it's", "about", "when",
    "what", "how", "while", "who", "where", "why"
}

def tokenize_text(text):
    """
    Tokenizes a string into a list of words (lowercased, no punctuation/digits,
    removing stopwords).
    """
    # Lowercase
    text = text.lower()
    # Remove punctuation and digits
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\d+", "", text)
    # Split on whitespace
    tokens = text.split()
    # Remove stopwords and short tokens
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    return tokens

def chat_gpt_analysis(prompt_text, model="gpt-3.5-turbo", temperature=0.7):
    """
    Send text to OpenAI's ChatCompletion API and return the content of the response.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant for analyzing text."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=temperature
    )
    return response.choices[0].message.content

def gpt_analyze_summaries_aggregate(df, summary_col="summary"):
    """
    Combine ALL summaries into a single text and analyze them in aggregate.
    Returns a single string: GPT's analysis of all the summaries together.
    """
    # Combine all summaries into one large block of text.
    all_summaries = "\n".join(df[summary_col].fillna("").astype(str))

    # You can adjust the prompt as you like.
    # For instance, you might ask for main themes, tone, patterns, etc.
    prompt = (
        "Here are the combined summaries from a set of YouTube thumbnails. "
        "Please provide an overall analysis, including any major themes, "
        "common topics, and recurring patterns you observe. Keep it concise:\n"
        "--------------------------------\n"
        f"{all_summaries}\n"
        "--------------------------------\n"
        "Provide a few paragraphs of overall insight."
    )

    try:
        gpt_response = chat_gpt_analysis(prompt_text=prompt)
        return gpt_response.strip()
    except Exception as e:
        print(f"Error generating aggregate GPT analysis: {e}")
        return "ERROR"

def generate_bar_chart(data_dict, title):
    """
    Generates a simple bar chart (in a new figure) and returns
    the base64-encoded PNG image as an <img> tag string.
    """
    labels = list(data_dict.keys())
    values = list(data_dict.values())

    plt.figure(figsize=(6, 4))
    plt.bar(labels, values)
    plt.title(title)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f'<img src="data:image/png;base64,{encoded}" alt="{title}" />'

def top_n_counter(counter_obj, n=10):
    """
    Given a Counter object, return the top n items.
    """
    return dict(islice(counter_obj.most_common(n), n))

def analyze_tokens_in_summaries(df, summary_col="summary"):
    """
    Basic word/bigram frequency analysis of the entire summary column (aggregate).
    Returns (top_words, top_bigrams) as dictionaries.
    """
    all_tokens = []
    all_bigrams = Counter()

    for summary in df[summary_col]:
        tokens = tokenize_text(summary)
        all_tokens.extend(tokens)
        for i in range(len(tokens) - 1):
            bigram = (tokens[i], tokens[i+1])
            all_bigrams[bigram] += 1

    word_counter = Counter(all_tokens)
    top_words = top_n_counter(word_counter, n=10)
    top_bigrams = top_n_counter(all_bigrams, n=10)
    return top_words, top_bigrams

def analyze_columns(df):
    """
    Generate bar charts for selected columns (if they are present). 
    Returns a dict: {column_name: <base64 image HTML>, ...}
    """
    columns_to_chart = ["color_category_strict", "text_style_category", "scene_classification"]
    charts = {}

    for col in columns_to_chart:
        if col in df.columns:
            counts = df[col].fillna('Missing').value_counts().head(10)
            data_dict = {str(k): int(v) for k, v in counts.items()}
            chart_html = generate_bar_chart(data_dict, f"{col} Distribution (Top 10)")
            charts[col] = chart_html

    return charts

def overall_analysis(df):
    """
    Returns an HTML string with relevant data:
    - Basic info
    - People Count distribution
    - CTA detection
    - Brand logos presence
    """
    buf = StringIO()
    df.info(buf=buf)
    info_text = buf.getvalue()

    lines = []
    lines.append("<h2>DataFrame Info</h2>")
    lines.append(f"<pre>{info_text}</pre>")

    # People Count
    if 'people_count' in df.columns:
        lines.append("<h2>People Count Distribution</h2>")
        people_count = df['people_count'].value_counts(dropna=False).sort_index()
        lines.append(f"<pre>{people_count}</pre>")

    # CTA Detection
    if 'cta_detected' in df.columns:
        lines.append("<h2>CTA Detected Distribution</h2>")
        cta_counts = df['cta_detected'].value_counts(dropna=False)
        lines.append(f"<pre>{cta_counts}</pre>")

    # Brand Logos
    if 'brand_logos' in df.columns:
        lines.append("<h2>Brand Logos Count</h2>")
        brand_count = df['brand_logos'].notnull().sum()
        lines.append(f"<p>Number of thumbnails with brand logos: <b>{brand_count}</b></p>")

    return "\n".join(lines)

def main():
    """
    Main function to:
    1. Load CSV
    2. Run GPT analysis on 'summary' column (aggregate)
    3. Basic token/bigram analysis
    4. Basic column distributions
    5. Generate HTML file with a single aggregated GPT result
    """
    # 1. Read CSV
    csv_file = "results/youtube_thumbnail_analysis_extended_20250321.csv"
    df = pd.read_csv(csv_file)

    # 2. GPT Analysis on ALL summaries in aggregate
    print("Analyzing all 'summary' rows in aggregate with GPT...this may take a while.")
    aggregate_gpt_response = gpt_analyze_summaries_aggregate(df, summary_col="summary")

    # 3. Basic token/bigram analysis
    top_words, top_bigrams = analyze_tokens_in_summaries(df, summary_col="summary")
    top_words_chart = generate_bar_chart(top_words, "Top 10 Words (Summary)")
    top_bigram_str = {f"{k[0]} {k[1]}": v for k, v in top_bigrams.items()}
    top_bigrams_chart = generate_bar_chart(top_bigram_str, "Top 10 Bigrams (Summary)")

    # 4. Column-based charts
    column_charts = analyze_columns(df)

    # 5. Generate HTML
    results_html = []
    results_html.append("<h1>Thumbnail Analysis with GPT (Aggregate Summary)</h1>")

    # Overall numeric analysis
    results_html.append(overall_analysis(df))

    # GPT's single aggregated analysis
    results_html.append("<h2>GPT Aggregate Analysis of All Summaries</h2>")
    results_html.append(f"<div style='border:1px solid #ccc; padding:10px;'>{aggregate_gpt_response}</div>")

    # Word/Bigram Analysis
    results_html.append("<h2>Deeper Text Analysis (Token-based)</h2>")
    results_html.append("<h3>Top 10 Words in Summaries (Aggregate)</h3>")
    results_html.append("<ul>")
    for w, c in top_words.items():
        results_html.append(f"<li>{w}: {c}</li>")
    results_html.append("</ul>")
    results_html.append(top_words_chart)

    results_html.append("<h3>Top 10 Bigrams in Summaries (Aggregate)</h3>")
    results_html.append("<ul>")
    for b_str, c in top_bigram_str.items():
        results_html.append(f"<li>{b_str}: {c}</li>")
    results_html.append("</ul>")
    results_html.append(top_bigrams_chart)

    # Column charts
    results_html.append("<h2>Selected Column Distributions</h2>")
    for col, chart_tag in column_charts.items():
        results_html.append(f"<h3>{col}</h3>")
        results_html.append(chart_tag)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8"/>
    <title>Thumbnail Analysis with GPT (Aggregate)</title>
</head>
<body>
    {'\n'.join(results_html)}
</body>
</html>
"""

    output_file = "results/analysis_results_gpt_aggregate.html"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nAnalysis complete. Results saved to '{output_file}'.")
    print("This report includes a single GPT analysis of all summaries combined.")

if __name__ == "__main__":
    main()

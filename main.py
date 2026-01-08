import feedparser
import requests
import os
import argparse
import sys
import datetime
import re
import json
import csv
from bs4 import BeautifulSoup

def sanitize_filename(filename):
    """Sanitize the filename to be safe for filesystems."""
    # Remove invalid characters
    s = re.sub(r'[\\/:*?"<>|]', '', filename)
    # Replace spaces with underscores could be an option, but keeping spaces is usually fine on modern OS.
    # Let's just strip leading/trailing whitespace.
    return s.strip()

def html_to_text(html_content):
    """Convert HTML content to clean plain text."""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup.get_text(separator='\n\n').strip()

def create_aggregated_file(output_dir, podcast_title):
    """Aggregate all .txt files into one master file."""
    # Exclude the aggregated file itself AND the download log
    txt_files = sorted([
        f for f in os.listdir(output_dir) 
        if f.endswith('.txt') 
        and "All_Transcripts" not in f
        and f != "download_log.txt"
    ])
    
    if not txt_files:
        return

    agg_filename = f"{sanitize_filename(podcast_title)}_All_Transcripts.txt"
    agg_path = os.path.join(output_dir, agg_filename)
    
    print(f"\nCreating aggregated file: {agg_filename}")
    
    with open(agg_path, 'w', encoding='utf-8') as outfile:
        outfile.write(f"AGGREGATED TRANSCRIPTS FOR: {podcast_title}\n")
        outfile.write(f"Generated: {datetime.datetime.now()}\n")
        outfile.write("="*80 + "\n\n")
        
        for fname in txt_files:
            file_path = os.path.join(output_dir, fname)
            try:
                with open(file_path, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    
                outfile.write(f"EPISODE: {fname}\n")
                outfile.write("-" * 80 + "\n")
                outfile.write(content)
                outfile.write("\n\n" + "="*80 + "\n\n")
            except Exception as e:
                print(f"Error reading {fname}: {e}")

def get_transcripts(rss_url, output_base='downloads'):
    print(f"Parsing feed: {rss_url}")
    
    # helper for requests to suppress warnings if we disable verify
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    try:
        # Use requests to fetch the feed so we can control SSL verification
        response = requests.get(rss_url, timeout=10, verify=False)
        response.raise_for_status()
        feed_content = response.content
        feed = feedparser.parse(feed_content)
    except Exception as e:
        print(f"Error fetching feed: {e}")
        return

    if feed.bozo:
        print(f"Warning: Malformed feed data detected. Error: {feed.bozo_exception}")

    if not hasattr(feed, 'feed') or not hasattr(feed.feed, 'title'):
        print("Error: Could not parse feed title. Is this a valid RSS feed?")
        return

    podcast_title = sanitize_filename(feed.feed.title)
    output_dir = os.path.join(output_base, podcast_title)
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Podcast Title: {feed.feed.title}")
    print(f"Saving to: {output_dir}")

    success_count = 0
    skip_count = 0
    fail_count = 0

    log_path = os.path.join(output_dir, "download_log.txt")
    csv_path = os.path.join(output_dir, "skipped_episodes.csv")
    
    # Initialize CSV if it doesn't exist
    if not os.path.exists(csv_path):
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Episode Title", "Reason", "Date", "Details"])

    with open(log_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f"--- Run started at {datetime.datetime.now()} ---\n")

        total_entries = len(feed.entries)
        print(f"Found {total_entries} episodes.")

        for i, entry in enumerate(feed.entries):
            episode_title = entry.get('title', f"Episode_{i}")
            safe_title = sanitize_filename(episode_title)
            
            # published date for sorting
            published = entry.get('published_parsed', None)
            if published:
                date_prefix = datetime.datetime(*published[:6]).strftime('%Y-%m-%d')
            else:
                date_prefix = "0000-00-00"

            # Check for transcript
            transcript_url = None
            transcript_type = None

            # Strategy 1: Look for 'podcast_transcript' key from feedparser
            if 'podcast_transcript' in entry:
                pt = entry['podcast_transcript']
                # could be a list or a single dict
                if isinstance(pt, list) and len(pt) > 0:
                    # just take the first one for now, or prioritize specific types?
                    # Let's simple take the first one.
                    transcript_url = pt[0].get('url')
                    transcript_type = pt[0].get('type')
                elif isinstance(pt, dict):
                    transcript_url = pt.get('url')
                    transcript_type = pt.get('type')

            # Strategy 2: Look in links with rel='transcript' (fallback)
            if not transcript_url and 'links' in entry:
                for link in entry.links:
                    if link.get('rel') == 'transcript':
                        transcript_url = link.get('href')
                        transcript_type = link.get('type')
                        break
            
            if not transcript_url:
                msg = f"No transcript found for: {episode_title}"
                # print(f"Skipping: {episode_title} (No transcript tag)") # Optional: reduce noise
                log_file.write(f"SKIP [No Tag]: {episode_title}\n")
                
                with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([episode_title, "No Tag", date_prefix, "No podcast:transcript tag found"])
                
                skip_count += 1
                continue

            # File extension guess
            ext = ".txt"
            if transcript_type == "application/json":
                ext = ".json"
            elif transcript_type == "text/vtt":
                ext = ".vtt"
            elif transcript_type == "application/srt":
                ext = ".srt"
            elif transcript_type == "text/html":
                ext = ".html"
            
            filename = f"{date_prefix}_{safe_title}{ext}"
            file_path = os.path.join(output_dir, filename)
            
            # If it's HTML, we only care if the .txt version exists
            check_path = file_path
            if ext == ".html":
                check_path = file_path.replace('.html', '.txt')

            if os.path.exists(check_path):
                # print(f"Exists: {filename}")
                log_file.write(f"SKIP [Exists]: {episode_title}\n")
                skip_count += 1
                continue

            # Download
            try:
                print(f"Downloading transcript for: {episode_title}")
                response = requests.get(transcript_url, timeout=10, verify=False)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                if ext == ".html":
                    # Parse HTML to text
                    text_content = html_to_text(response.content)
                    
                    txt_filename = filename.replace('.html', '.txt')
                    txt_path = os.path.join(output_dir, txt_filename)

                    # Save as .txt
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(text_content)
                    
                    print(f"       Converted to: {txt_filename}")
                    log_file.write(f"SUCCESS: {episode_title} -> {txt_filename} (from HTML)\n")
                    success_count += 1
                else:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    log_file.write(f"SUCCESS: {episode_title} -> {filename}\n")
                    success_count += 1

            except Exception as e:
                print(f"Failed to download {episode_title}: {e}")
                log_file.write(f"ERROR: {episode_title} - {e}\n")
                
                with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([episode_title, "Download Error", date_prefix, str(e)])
                
                fail_count += 1

    print(f"\nDone. Success: {success_count}, Skipped: {skip_count}, Failed: {fail_count}")

    # Aggregate transcripts
    create_aggregated_file(output_dir, podcast_title)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download podcast transcripts from an RSS feed.")
    parser.add_argument("url", help="RSS Feed URL")
    parser.add_argument("--output", default="downloads", help="Output directory")
    
    args = parser.parse_args()
    
    get_transcripts(args.url, args.output)

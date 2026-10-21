"""
Step 3: Import Talk Data to Supabase
======================================
Reads scripts/output/talks.json, splits each talk into sentences,
imports the text records to Supabase (without embeddings), and
saves the sentence records locally for the embedding step.

After this step, KEYWORD SEARCH will light up green on your site!
Embeddings are added in the next step to enable semantic search.

Usage:
    python scripts/03_import_data.py

Input:
    scripts/output/talks.json  — from Step 2 (scraping)

Output:
    scripts/output/sentences.json  — sentence records with talk_id + sentence_num

Prerequisites:
    - config.public.json with Supabase URL and publishable key
    - config.secret.json with Supabase service key
    - Database schema created (Step 1)
    - Talks scraped (Step 2)
"""

import argparse
import json
import os
import re
import sys
import time
import uuid

from supabase import create_client
from tqdm import tqdm


INPUT_FILE = os.path.join('scripts', 'output', 'talks.json')
OUTPUT_FILE = os.path.join('scripts', 'output', 'sentences.json')
BATCH_SIZE = 100


def load_config():
    with open('config.public.json', 'r') as f:
        public_config = json.load(f)
    with open('config.secret.json', 'r') as f:
        secrets = json.load(f)
    required = {
        'SUPABASE_URL': public_config.get('SUPABASE_URL'),
        'SUPABASE_SERVICE_KEY': secrets.get('SUPABASE_SERVICE_KEY'),
    }
    missing = [name for name, value in required.items() if not value or 'YOUR_' in value]
    if missing:
        raise ValueError(f"Fill in these settings before continuing: {', '.join(missing)}")
    return public_config, secrets


def split_into_sentences(text):
    """Split text into sentences using a simple heuristic."""
    sentences = re.split(r'\. (?=[A-Z])', text)
    sentences = [s.strip() + '.' if not s.endswith('.') else s.strip() for s in sentences]
    return [s for s in sentences if len(s) > 20]


def main():
    parser = argparse.ArgumentParser(description='Import scraped talk sentences into Supabase.')
    parser.add_argument('--replace', action='store_true', help='Delete existing sentence rows before importing.')
    parser.add_argument('--yes', action='store_true', help='Skip the confirmation prompt when using --replace.')
    args = parser.parse_args()

    if not os.path.exists(INPUT_FILE):
        print(f"❌ {INPUT_FILE} not found. Run scripts/02_scrape_data.py first.")
        sys.exit(1)

    # Load talks
    print("=" * 60)
    print("Importing Talk Data to Supabase")
    print("=" * 60)

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        talks = json.load(f)
    if not isinstance(talks, list) or not talks:
        print(f"❌ {INPUT_FILE} is empty or is not a list of talks.")
        sys.exit(1)
    print(f"   Loaded {len(talks)} talks\n")

    # Split into sentence records (no embeddings yet)
    print("Splitting talks into sentences...")
    sentence_records = []
    for talk in tqdm(talks, desc="Splitting"):
        # Stable IDs make talk grouping consistent across repeated pipeline runs.
        talk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, talk['url']))
        sentences = split_into_sentences(talk['text'])
        for i, sentence in enumerate(sentences, 1):
            sentence_records.append({
                'talk_id': talk_id,
                'title': talk['title'],
                'speaker': talk['speaker'],
                'calling': talk['calling'],
                'year': int(talk['year']) if talk['year'] else None,
                'season': talk['season'],
                'url': talk['url'],
                'sentence_num': i,
                'text': sentence
                # No 'embedding' field — added in next step
            })

    print(f"✅ Split {len(talks)} talks into {len(sentence_records):,} sentences")
    print(f"   Average: {len(sentence_records) / len(talks):.1f} sentences per talk\n")

    # Save sentences locally (for embedding step to use)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(sentence_records, f, ensure_ascii=False)
    file_size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"💾 Saved {len(sentence_records):,} sentences to {OUTPUT_FILE} ({file_size_mb:.1f} MB)")

    # Connect to Supabase
    try:
        public_config, secrets = load_config()
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"❌ Could not load Supabase credentials: {e}")
        sys.exit(1)
    client = create_client(public_config['SUPABASE_URL'], secrets['SUPABASE_SERVICE_KEY'])

    # Avoid deleting existing rows unless the user explicitly requests replacement.
    print("\n" + "=" * 60)
    print("Checking for existing data...")
    print("=" * 60)

    try:
        result = client.table('sentence_embeddings').select('id', count='exact').limit(1).execute()
        existing_count = result.count or 0
        if existing_count > 0 and args.replace:
            print(f"   This will delete all {existing_count:,} existing sentence rows.")
            if not args.yes:
                confirmation = input("Type REPLACE to continue: ").strip()
                if confirmation != 'REPLACE':
                    print('Cancelled. Existing rows were not changed.')
                    sys.exit(1)
            client.table('sentence_embeddings').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
            print("   ✅ Existing rows deleted.")
        elif existing_count > 0:
            print(f"   Found {existing_count:,} existing rows. Matching sentences will be skipped; no rows will be deleted.")
            print("   Use --replace only if you intentionally want to reset the whole table.")
        else:
            print("   Table is empty — ready for import.")
    except Exception as e:
        print(f"   ❌ Could not verify existing data safely: {e}")
        print("   Stopping before import so existing rows cannot be overwritten accidentally.")
        sys.exit(1)

    # Import in batches
    print("\n" + "=" * 60)
    print(f"Importing {len(sentence_records):,} records to Supabase")
    print("=" * 60)
    print("   (Text only — embeddings will be added in the next step)\n")

    errors = 0

    for i in tqdm(range(0, len(sentence_records), BATCH_SIZE), desc="Importing"):
        batch = sentence_records[i:i + BATCH_SIZE]
        try:
            client.table('sentence_embeddings').upsert(
                batch,
                on_conflict='talk_id,sentence_num',
                ignore_duplicates=True,
            ).execute()
        except Exception as e:
            print(f"\nError at batch {i // BATCH_SIZE}: {e}")
            errors += len(batch)
        time.sleep(0.1)

    print(f"\nImport finished.")
    print(f"   Submitted: {len(sentence_records):,}")
    if errors:
        print(f"   Errors:  {errors:,}")
        print("   Some batches failed; do not continue to embedding until the import is complete.")
        sys.exit(1)

    # Final verification
    target_talk_ids = list({record['talk_id'] for record in sentence_records})
    imported_count = 0
    for start in range(0, len(target_talk_ids), 100):
        result = client.table('sentence_embeddings') \
            .select('id', count='exact') \
            .in_('talk_id', target_talk_ids[start:start + 100]) \
            .limit(1).execute()
        imported_count += result.count or 0
    total_count = client.table('sentence_embeddings').select('id', count='exact').limit(1).execute().count or 0
    print(f"\n   Rows for scraped talks: {imported_count:,}")
    print(f"   Total rows in database: {total_count:,}")
    if imported_count != len(sentence_records):
        print(f"❌ Expected {len(sentence_records):,} rows for these talks but found {imported_count:,}.")
        sys.exit(1)

    print(f"\n🎉 Keyword Search is now ready!")
    print(f"   Refresh your site — the 🔍 Keyword Search panel should turn GREEN.")
    print(f"\nNext: python scripts/04_embed_data.py")


if __name__ == '__main__':
    main()

"""
Step 4: Generate and locally checkpoint text embeddings.

The output is resumable by (talk_id, sentence_num), so a failed batch can be
retried without paying again for successful records.
"""

import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / 'scripts' / 'output' / 'sentences.json'
OUTPUT_FILE = ROOT / 'scripts' / 'output' / 'sentences_with_embeddings.json'
BATCH_SIZE = 100
EMBEDDING_DIMENSIONS = 1_536


def record_key(record):
    return (record.get('talk_id'), record.get('sentence_num'))


def save_checkpoint(records):
    temporary_file = OUTPUT_FILE.with_suffix('.json.tmp')
    with temporary_file.open('w', encoding='utf-8') as file:
        json.dump(records, file, ensure_ascii=False)
    os.replace(temporary_file, OUTPUT_FILE)


def main():
    if not INPUT_FILE.exists():
        print(f'❌ {INPUT_FILE.relative_to(ROOT)} not found. Run scripts/03_import_data.py first.')
        sys.exit(1)

    records = json.loads(INPUT_FILE.read_text(encoding='utf-8'))
    if not isinstance(records, list) or not records or any(not isinstance(record, dict) for record in records):
        print('❌ Sentence input is empty or invalid.')
        sys.exit(1)

    secrets_path = ROOT / 'config.secret.json'
    try:
        secrets = json.loads(secrets_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        print(f'❌ Could not read config.secret.json: {error}')
        sys.exit(1)
    api_key = secrets.get('OPENAI_API_KEY')
    if not api_key or 'YOUR_' in api_key:
        print('❌ Add your OPENAI_API_KEY to the git-ignored config.secret.json before embedding.')
        sys.exit(1)

    embedded_by_key = {}
    if OUTPUT_FILE.exists():
        try:
            previous = json.loads(OUTPUT_FILE.read_text(encoding='utf-8'))
            if not isinstance(previous, list):
                raise ValueError('Checkpoint must be a JSON list.')
            embedded_by_key = {
                record_key(record): record
                for record in previous
                if isinstance(record, dict)
                and isinstance(record.get('embedding'), list)
                and len(record['embedding']) == EMBEDDING_DIMENSIONS
            }
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            print(f'❌ Existing embedding checkpoint is invalid: {error}')
            sys.exit(1)

    pending = [record for record in records if record_key(record) not in embedded_by_key]
    print('=' * 60)
    print(f'Generating embeddings for {len(records):,} sentences')
    print(f'Already complete: {len(records) - len(pending):,}; remaining: {len(pending):,}')
    print(f'Model: text-embedding-3-small ({EMBEDDING_DIMENSIONS:,} dimensions)')
    print('=' * 60)

    client = OpenAI(api_key=api_key)
    failed = 0
    for start in tqdm(range(0, len(pending), BATCH_SIZE), desc='Embedding'):
        batch = pending[start:start + BATCH_SIZE]
        batch_failed = False
        try:
            response = client.embeddings.create(
                model='text-embedding-3-small',
                input=[record['text'] for record in batch],
            )
            data = sorted(response.data, key=lambda item: item.index)
            if len(data) != len(batch):
                raise ValueError(f'Expected {len(batch)} vectors, received {len(data)}.')
            for record, item in zip(batch, data):
                if len(item.embedding) != EMBEDDING_DIMENSIONS:
                    raise ValueError('OpenAI returned a vector with an unexpected dimension.')
                embedded_by_key[record_key(record)] = {**record, 'embedding': item.embedding}
        except Exception as error:
            failed += len(batch)
            batch_failed = True
            print(f'\n❌ Batch beginning at sentence {start:,} failed: {error}')

        if batch_failed or (start // BATCH_SIZE + 1) % 10 == 0:
            save_checkpoint([
                embedded_by_key[key]
                for key in (record_key(record) for record in records)
                if key in embedded_by_key
            ])
        time.sleep(0.1)

    completed_records = [
        embedded_by_key[record_key(record)]
        for record in records
        if record_key(record) in embedded_by_key
    ]
    save_checkpoint(completed_records)

    missing = len(records) - len(completed_records)
    print(f'\nSaved {len(completed_records):,} vectors to {OUTPUT_FILE.relative_to(ROOT)}.')
    if failed or missing:
        print(f'⚠️ {missing:,} vectors remain. Run this script again to retry the missing records.')
        sys.exit(1)

    total_chars = sum(len(record['text']) for record in records)
    estimated_tokens = total_chars / 4
    estimated_cost = estimated_tokens / 1_000_000 * 0.020
    print(f'✅ All {len(completed_records):,} sentences embedded.')
    print(f'   Rough embedding cost estimate: ${estimated_cost:.4f}')
    print('Next: python scripts/05_update_embeddings.py')


if __name__ == '__main__':
    main()

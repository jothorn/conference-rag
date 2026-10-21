"""Pipeline stage 4: turn each sentence into a vector and save progress locally.

The checkpoint is keyed by (talk_id, sentence_num), so the script can resume
after a failed batch without requesting embeddings for completed sentences again.
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


def sentence_key(record):
    """Return the stable identifier shared by import and embedding records."""
    return (record.get('talk_id'), record.get('sentence_num'))


def load_sentence_records():
    """Read the text-only records produced by the import stage."""
    if not INPUT_FILE.exists():
        print(f'❌ {INPUT_FILE.relative_to(ROOT)} not found. Run scripts/03_import_data.py first.')
        sys.exit(1)

    records = json.loads(INPUT_FILE.read_text(encoding='utf-8'))
    if not isinstance(records, list) or not records or any(not isinstance(row, dict) for row in records):
        print('❌ Sentence input is empty or invalid.')
        sys.exit(1)
    return records


def load_openai_api_key():
    """Load the local key used only by this offline batch step."""
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
    return api_key


def load_completed_embeddings():
    """Read valid vectors from the checkpoint and index them by sentence ID."""
    if not OUTPUT_FILE.exists():
        return {}

    try:
        checkpoint = json.loads(OUTPUT_FILE.read_text(encoding='utf-8'))
        if not isinstance(checkpoint, list):
            raise ValueError('Checkpoint must be a JSON list.')
        return {
            sentence_key(row): row
            for row in checkpoint
            if isinstance(row, dict)
            and isinstance(row.get('embedding'), list)
            and len(row['embedding']) == EMBEDDING_DIMENSIONS
        }
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        print(f'❌ Existing embedding checkpoint is invalid: {error}')
        sys.exit(1)


def embed_batch(client, records):
    """Request vectors and pair them with their source sentences by API index."""
    response = client.embeddings.create(
        model='text-embedding-3-small',
        input=[record['text'] for record in records],
    )
    vectors = sorted(response.data, key=lambda item: item.index)
    if len(vectors) != len(records):
        raise ValueError(f'Expected {len(records)} vectors, received {len(vectors)}.')

    embedded_records = []
    for record, vector in zip(records, vectors):
        if len(vector.embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError('OpenAI returned a vector with an unexpected dimension.')
        embedded_records.append({**record, 'embedding': vector.embedding})
    return embedded_records


def save_checkpoint(records, embeddings_by_key):
    """Atomically save completed vectors in the same order as the input file."""
    completed = [
        embeddings_by_key[sentence_key(record)]
        for record in records
        if sentence_key(record) in embeddings_by_key
    ]
    temporary_file = OUTPUT_FILE.with_suffix('.json.tmp')
    with temporary_file.open('w', encoding='utf-8') as file:
        json.dump(completed, file, ensure_ascii=False)
    os.replace(temporary_file, OUTPUT_FILE)
    return completed


def embed_pending_records(records, embeddings_by_key, client):
    """Generate only missing vectors, checkpointing regularly and after errors."""
    pending = [record for record in records if sentence_key(record) not in embeddings_by_key]
    failed_rows = 0

    for batch_number, start in enumerate(tqdm(range(0, len(pending), BATCH_SIZE), desc='Embedding'), start=1):
        batch = pending[start:start + BATCH_SIZE]
        batch_failed = False
        try:
            completed_batch = embed_batch(client, batch)
            embeddings_by_key.update({sentence_key(row): row for row in completed_batch})
        except Exception as error:
            failed_rows += len(batch)
            print(f'\n❌ Batch beginning at sentence {start:,} failed: {error}')
            batch_failed = True

        # Limit lost work if the process stops unexpectedly during a long run.
        if batch_failed or batch_number % 10 == 0:
            save_checkpoint(records, embeddings_by_key)
        time.sleep(0.1)

    return failed_rows


def main():
    records = load_sentence_records()
    api_key = load_openai_api_key()
    embeddings_by_key = load_completed_embeddings()
    pending_count = sum(sentence_key(row) not in embeddings_by_key for row in records)

    print('=' * 60)
    print(f'Generating embeddings for {len(records):,} sentences')
    print(f'Already complete: {len(records) - pending_count:,}; remaining: {pending_count:,}')
    print(f'Model: text-embedding-3-small ({EMBEDDING_DIMENSIONS:,} dimensions)')
    print('=' * 60)

    failed_rows = embed_pending_records(records, embeddings_by_key, OpenAI(api_key=api_key))
    completed = save_checkpoint(records, embeddings_by_key)
    missing_count = len(records) - len(completed)

    print(f'\nSaved {len(completed):,} vectors to {OUTPUT_FILE.relative_to(ROOT)}.')
    if failed_rows or missing_count:
        print(f'⚠️ {missing_count:,} vectors remain. Run this script again to retry the missing records.')
        sys.exit(1)

    estimated_tokens = sum(len(record['text']) for record in records) / 4
    estimated_cost = estimated_tokens / 1_000_000 * 0.020
    print(f'✅ All {len(completed):,} sentences embedded.')
    print(f'   Rough embedding cost estimate: ${estimated_cost:.4f}')
    print('Next: python scripts/05_update_embeddings.py')


if __name__ == '__main__':
    main()

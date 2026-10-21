"""Pipeline stage 5: upload the locally generated vectors to Supabase.

Rows are upserted by (talk_id, sentence_num), so retrying a failed run updates
the matching sentences instead of deleting or duplicating the dataset.
"""

import json
import sys
import time
from pathlib import Path

from supabase import create_client
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / 'scripts' / 'output' / 'sentences_with_embeddings.json'
BATCH_SIZE = 25
EMBEDDING_DIMENSIONS = 1_536


def load_config():
    """Load the public project URL and local service key for this batch job."""
    public_config = json.loads((ROOT / 'config.public.json').read_text(encoding='utf-8'))
    secrets = json.loads((ROOT / 'config.secret.json').read_text(encoding='utf-8'))
    required = {
        'SUPABASE_URL': public_config.get('SUPABASE_URL'),
        'SUPABASE_SERVICE_KEY': secrets.get('SUPABASE_SERVICE_KEY'),
    }
    missing = [name for name, value in required.items() if not value or 'YOUR_' in value]
    if missing:
        raise ValueError(f"Fill in these settings before continuing: {', '.join(missing)}")
    return public_config, secrets


def load_embedding_records():
    """Read the checkpoint and reject rows missing a 1,536-value vector."""
    if not INPUT_FILE.exists():
        print(f'❌ {INPUT_FILE.relative_to(ROOT)} not found. Run scripts/04_embed_data.py first.')
        sys.exit(1)

    records = json.loads(INPUT_FILE.read_text(encoding='utf-8'))
    if not isinstance(records, list) or not records:
        print('❌ Embedding input is empty or invalid.')
        sys.exit(1)

    invalid_count = sum(
        not isinstance(record, dict)
        or not isinstance(record.get('embedding'), list)
        or len(record['embedding']) != EMBEDDING_DIMENSIONS
        or not record.get('talk_id')
        or not record.get('sentence_num')
        for record in records
    )
    if invalid_count:
        print(f'❌ {invalid_count:,} records lack a valid {EMBEDDING_DIMENSIONS:,}-dimensional embedding.')
        print('   Run scripts/04_embed_data.py again to complete the embedding checkpoint.')
        sys.exit(1)
    return records


def upload_embeddings(client, records):
    """Upsert each batch; return the number of rows in failed batches."""
    failed_rows = 0
    for start in tqdm(range(0, len(records), BATCH_SIZE), desc='Importing embeddings'):
        batch = records[start:start + BATCH_SIZE]
        try:
            client.table('sentence_embeddings').upsert(
                batch,
                on_conflict='talk_id,sentence_num',
            ).execute()
        except Exception as error:
            failed_rows += len(batch)
            print(f'\n❌ Batch beginning at row {start:,} failed: {error}')
        time.sleep(0.1)
    return failed_rows


def count_rows(client):
    """Return total and embedded row counts using exact PostgREST counts."""
    total = client.table('sentence_embeddings').select('id', count='exact').limit(1).execute().count or 0
    embedded = client.table('sentence_embeddings') \
        .select('id', count='exact') \
        .not_.is_('embedding', 'null') \
        .limit(1).execute().count or 0
    return total, embedded


def main():
    try:
        records = load_embedding_records()
        public_config, secrets = load_config()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f'❌ Could not load inputs or credentials: {error}')
        sys.exit(1)

    client = create_client(public_config['SUPABASE_URL'], secrets['SUPABASE_SERVICE_KEY'])
    print(f'Upserting {len(records):,} embedded sentence rows in batches of {BATCH_SIZE}.')
    failed_rows = upload_embeddings(client, records)
    if failed_rows:
        print(f'❌ {failed_rows:,} rows did not upsert. Re-run this script to retry safely.')
        sys.exit(1)

    total_rows, embedded_rows = count_rows(client)
    print('\n✅ Embedding import complete.')
    print(f'   Rows in database: {total_rows:,}')
    print(f'   Rows with embeddings: {embedded_rows:,}')
    if embedded_rows < len(records):
        print(f'❌ Expected at least {len(records):,} embedded rows; found {embedded_rows:,}.')
        sys.exit(1)
    print('Semantic search is ready. Next: deploy the Edge Functions.')


if __name__ == '__main__':
    main()

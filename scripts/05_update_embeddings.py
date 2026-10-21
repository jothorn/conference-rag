"""
Step 5: Upsert embedded sentences into Supabase.

Re-running this step updates the matching (talk_id, sentence_num) rows instead
of truncating the table. A partially completed import is safe to resume.
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


def main():
    if not INPUT_FILE.exists():
        print(f'❌ {INPUT_FILE.relative_to(ROOT)} not found. Run scripts/04_embed_data.py first.')
        sys.exit(1)

    try:
        records = json.loads(INPUT_FILE.read_text(encoding='utf-8'))
        public_config, secrets = load_config()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f'❌ Could not load inputs or credentials: {error}')
        sys.exit(1)

    if not isinstance(records, list) or not records:
        print('❌ Embedding input is empty or invalid.')
        sys.exit(1)
    invalid = [
        index for index, record in enumerate(records)
        if not isinstance(record, dict)
        or not isinstance(record.get('embedding'), list)
        or len(record['embedding']) != EMBEDDING_DIMENSIONS
        or not record.get('talk_id')
        or not record.get('sentence_num')
    ]
    if invalid:
        print(f'❌ {len(invalid):,} records lack a valid 1,536-dimensional embedding.')
        print('   Run scripts/04_embed_data.py again to complete the embedding checkpoint.')
        sys.exit(1)

    client = create_client(public_config['SUPABASE_URL'], secrets['SUPABASE_SERVICE_KEY'])
    print(f'Upserting {len(records):,} embedded sentence rows in batches of {BATCH_SIZE}.')
    errors = 0
    for start in tqdm(range(0, len(records), BATCH_SIZE), desc='Importing embeddings'):
        batch = records[start:start + BATCH_SIZE]
        try:
            client.table('sentence_embeddings').upsert(
                batch,
                on_conflict='talk_id,sentence_num',
            ).execute()
        except Exception as error:
            errors += len(batch)
            print(f'\n❌ Batch beginning at row {start:,} failed: {error}')
        time.sleep(0.1)

    if errors:
        print(f'❌ {errors:,} rows did not upsert. Re-run this script to retry safely.')
        sys.exit(1)

    total = client.table('sentence_embeddings').select('id', count='exact').limit(1).execute().count or 0
    embedded = client.table('sentence_embeddings') \
        .select('id', count='exact') \
        .not_.is_('embedding', 'null') \
        .limit(1).execute().count or 0

    print('\n✅ Embedding import complete.')
    print(f'   Rows in database: {total:,}')
    print(f'   Rows with embeddings: {embedded:,}')
    if embedded < len(records):
        print(f'❌ Expected at least {len(records):,} embedded rows; found {embedded:,}.')
        sys.exit(1)
    print('Semantic search is ready. Next: deploy the Edge Functions.')


if __name__ == '__main__':
    main()

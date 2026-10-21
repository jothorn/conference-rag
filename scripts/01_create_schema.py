"""
Step 1: Create the Supabase schema from the checked-in SQL migration.

Usage:
    python scripts/01_create_schema.py

Required configuration:
    config.public.json: SUPABASE_URL
    config.secret.json: SUPABASE_ACCESS_TOKEN, SUPABASE_PROJECT_REF,
                        SUPABASE_SERVICE_KEY
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / 'supabase' / 'migrations' / '20261021220000_initial_schema.sql'


def load_config():
    with (ROOT / 'config.public.json').open(encoding='utf-8') as file:
        public_config = json.load(file)
    with (ROOT / 'config.secret.json').open(encoding='utf-8') as file:
        secrets = json.load(file)

    required = {
        'SUPABASE_URL': public_config.get('SUPABASE_URL'),
        'SUPABASE_ACCESS_TOKEN': secrets.get('SUPABASE_ACCESS_TOKEN'),
        'SUPABASE_PROJECT_REF': secrets.get('SUPABASE_PROJECT_REF'),
        'SUPABASE_SERVICE_KEY': secrets.get('SUPABASE_SERVICE_KEY'),
    }
    missing = [name for name, value in required.items() if not value or 'YOUR_' in value]
    if missing:
        raise ValueError(f"Fill in these settings before continuing: {', '.join(missing)}")
    return public_config, secrets


def create_schema():
    import requests
    from supabase import create_client

    if not MIGRATION.is_file():
        raise FileNotFoundError(f'Migration not found: {MIGRATION}')
    public_config, secrets = load_config()
    schema_sql = MIGRATION.read_text(encoding='utf-8')

    print('=' * 60)
    print('Applying Conference RAG schema migration')
    print('=' * 60)

    url = f"https://api.supabase.com/v1/projects/{secrets['SUPABASE_PROJECT_REF']}/database/query"
    headers = {
        'Authorization': f"Bearer {secrets['SUPABASE_ACCESS_TOKEN']}",
        'Content-Type': 'application/json',
    }
    response = requests.post(url, headers=headers, json={'query': schema_sql}, timeout=60)
    if response.status_code not in (200, 201):
        print(f'❌ Schema migration failed: HTTP {response.status_code}')
        print(response.text[:1_000])
        return False

    client = create_client(public_config['SUPABASE_URL'], secrets['SUPABASE_SERVICE_KEY'])
    for attempt in range(5):
        try:
            result = client.table('sentence_embeddings').select('id', count='exact').limit(1).execute()
            speakers = client.rpc('list_speakers').execute()
            print('✅ Schema verified.')
            print(f"   Current sentence rows: {result.count or 0:,}")
            print(f"   Speaker filter function: {len(speakers.data or [])} speakers found")
            return True
        except Exception as error:
            if attempt < 4:
                print(f'   Waiting for PostgREST to refresh its schema cache ({attempt + 1}/5)...')
                time.sleep(3)
            else:
                print(f'⚠️ Migration applied, but the schema verification query failed: {error}')
                return False


if __name__ == '__main__':
    try:
        ok = create_schema()
    except Exception as error:
        print(f'❌ Could not create schema: {error}')
        ok = False
    if not ok:
        sys.exit(1)
    print('\n✅ Schema ready. Next: python scripts/02_scrape_data.py')

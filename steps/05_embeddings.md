# Step 5: Embeddings & Semantic Search — 🧠 Second Green Light!

```
  🏁 LAUNCH ──→ 🔐 SIGN IN ──→ ✅ KEYWORD ──→ ▶ 🧠 SEMANTIC ──→ 🤖 RAG ──→ 🚀 YOURS
                                                   ~~~~~~~~~~~~
                                                   YOU ARE HERE
```

## What You'll Learn

- How embeddings represent text as vectors
- Why this project uses sentence-level chunks
- How pgvector ranks semantic matches
- Why an Edge Function keeps API keys out of browser code

## Step 5a: Generate embeddings

```bash
python scripts/04_embed_data.py
```

The script reads `scripts/output/sentences.json`, calls OpenAI's
`text-embedding-3-small` model, and saves vectors to
`scripts/output/sentences_with_embeddings.json`. It checkpoints results and
resumes by sentence ID after a failed batch. The assignment estimates about
$0.60 in API usage for the full dataset. It will not run until a real
`OPENAI_API_KEY` is in your git-ignored `config.secret.json`.

## Step 5b: Import the embeddings

```bash
python scripts/05_update_embeddings.py
```

This upserts rows by `(talk_id, sentence_num)` in small batches, so rerunning
it is safe after an interrupted import.

## Step 5c: Deploy `embed-question`

The function source is included at `supabase/functions/embed-question/`. It
validates the signed-in user's JWT, sends the question to OpenAI from the
server, and returns the 1,536-dimensional embedding. The OpenAI key never goes
to the browser.

Install the [Supabase CLI](https://supabase.com/docs/guides/cli), then log in
and link this local folder to the project reference in `config.secret.json`:

```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF
```

Copy the ignored env-file template, put the OpenAI key in it, and upload the
secrets. This keeps the key out of command history and Git:

```bash
cp supabase/functions/.env.example supabase/functions/.env
# Edit supabase/functions/.env and set OPENAI_API_KEY
supabase secrets set --env-file supabase/functions/.env
```

The project config disables gateway JWT verification because the function
validates the token itself with Supabase Auth. Deploy it with:

```bash
supabase functions deploy embed-question
```

## Verification

- [ ] `04_embed_data.py` completes and saves the embedding file
- [ ] `05_update_embeddings.py` reports the database row counts
- [ ] `embed-question` is deployed
- [ ] Semantic Search turns green and returns meaning-based results

## → Next: [Step 06: RAG — All Lights Green](06_rag.md)

# Step 6: RAG — 🤖 All Lights Green!

```
  🏁 LAUNCH ──→ 🔐 SIGN IN ──→ ✅ KEYWORD ──→ ✅ SEMANTIC ──→ ▶ 🤖 RAG ──→ 🚀 YOURS
                                                                  ~~~~~~~
                                                                  YOU ARE HERE
```

## What You'll Learn

- How retrieval-augmented generation combines database search and an LLM
- Why retrieved sources help ground answers
- How to bound context sent to a model

## Why this matters

Keyword search finds matching wording. Semantic search finds related meaning.
RAG retrieves likely relevant passages, gives them to a model with the
question, then shows the generated answer alongside links to its source talks.
The model can still be wrong; citations help readers check the evidence.

## Deploy `generate-answer`

The function source is included at
`supabase/functions/generate-answer/`. It validates the signed-in user's JWT,
accepts up to three bounded source talks, and calls GPT-4o using the
server-side OpenAI key. Its prompt treats talk text as quoted data and asks the
model to cite the exact talk title and speaker.

If you completed Step 5, the CLI is already linked and the OpenAI key and
allowed origins are set as Supabase secrets. Deploy the function:

```bash
supabase functions deploy generate-answer
```

## What's happening behind the scenes

```text
Question from the browser
    ↓
embed-question Edge Function
    → OpenAI returns a 1,536-dimensional question vector
    ↓
match_sentences(query_embedding, speaker_filter)
    → pgvector ranks similar sentences; optional speaker filter applies here
    ↓
Group by talk, then fetch full text for the top three talks
    ↓
generate-answer Edge Function
    → GPT-4o receives bounded text and returns an answer with citations
    ↓
Answer and source links appear in the browser
```

## Try it

1. Refresh the site and sign in.
2. Confirm all three panels are green.
3. Ask, “What have church leaders taught about prayer?”
4. Choose a speaker and ask again; every mode should stay within that speaker's talks.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Search shows “Not Ready” | Check data import, embeddings, and Edge Function deployment for that mode. |
| “Failed to get embedding” | Confirm `OPENAI_API_KEY` is set as a Supabase secret and `embed-question` is deployed. |
| No search results | Check the row count or clear the speaker filter. |
| Login does not work | Add your GitHub Pages URL to Supabase Auth redirect URLs. |
| Changes do not appear | Hard refresh or open the page in a private window. |

## Verification

- [ ] `generate-answer` is deployed
- [ ] All search modes turn green after sign-in
- [ ] Keyword and semantic search return talks
- [ ] RAG returns an answer and source links
- [ ] Speaker filter applies to all three modes
- [ ] Save a screenshot of a working RAG question for the submission

## → Next: [Step 07: Make It Yours](07_make_it_yours.md)

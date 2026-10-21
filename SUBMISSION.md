# Conference RAG Project Submission

## Project links

- Repository: <https://github.com/jothorn/conference-rag>
- Live site: <https://jothorn.github.io/conference-rag/>
- Working RAG screenshot: add a screenshot after connecting Supabase, importing the data, and deploying both Edge Functions.

## Custom feature: speaker filter across all search modes

The app has one speaker selector shared by keyword search, semantic search, and RAG. The `list_speakers()` SQL function supplies the selector. Keyword search filters its table query by the selected speaker. Semantic and RAG pass the same selection to `match_sentences()`, so vector retrieval is limited before RAG groups sources and sends context to the answer function. Selecting “All speakers” passes a null filter and keeps the original behavior.

This feature demonstrates how a single product control maps through three layers: the browser query, a Postgres function parameter, and the retrieval context used by generation. The SQL functions run as the authenticated caller and the sentence table remains protected by RLS.

## Reflection answers

These are technically grounded draft answers based on the implementation. Personal statements in question 5 should be edited to match the student's experience.

### 1. Security architecture

```text
Browser (GitHub Pages)
  ├─ public Supabase URL + anon/publishable key
  │    └─ RLS + SQL grants restrict database access
  ├─ signed-in user's JWT ───────────────┐
  └─ query and question text             │
                                         ▼
                              Supabase Edge Function
                                ├─ validates JWT with Supabase Auth
                                ├─ reads OPENAI_API_KEY from server secret
                                └─ sends bounded request to OpenAI
```

The publishable key identifies the Supabase project; it is intentionally public. It does not bypass database permissions. RLS and SQL grants decide which rows and operations the `anon` or `authenticated` roles can use. In this app, authenticated users can read talk sentences, while unauthenticated visitors only receive the deliberately public page-view behavior. RLS protects the database even if browser code is changed or bypassed.

The service-role key bypasses RLS. Someone who obtained it could read, change, or delete data regardless of browser policies, so it must stay in local ignored configuration or trusted server-side secrets and be rotated if exposed. The OpenAI key is stored as a Supabase Edge Function secret and is never sent to the browser. The functions separately verify the signed-in user's JWT before calling OpenAI. CORS limits which browser origins can read responses, but authentication and server-side validation are the access controls.

### 2. Edge Functions as the secure middle

The browser cannot safely call OpenAI with a private API key: browser code and network requests are visible to users. Instead, the Supabase client sends the user's JWT to an Edge Function. The function validates it with Supabase Auth, checks request sizes and fields, reads the OpenAI key from its server environment, calls OpenAI, and returns only the needed result. JWT validation proves that the request belongs to an authenticated Supabase user; it does not replace input limits or database RLS. The same server-side proxy pattern applies to payment providers, email services, and other APIs whose credentials must remain private.

### 3. SQL keyword search and semantic search

Keyword search uses `ILIKE` to match a text substring. It works well when the user remembers the wording, such as searching for “gratitude.” It can miss a question like “How can I keep going when life is difficult?” if a talk uses “persevere” or “endure” instead. Semantic search turns each sentence and query into 1,536-number vectors, then ranks sentences by cosine similarity with pgvector. The model's learned associations place related expressions near each other, so retrieval can bridge vocabulary differences. This is statistical similarity, not human understanding; low-quality embeddings or irrelevant context can still return poor matches.

### 4. RAG and fine-tuning

RAG retrieves source passages at question time, sends those passages with the question to a language model, and displays the answer with source talks. Updating the source collection does not require training a new model, and the retrieved passages make it easier to inspect where an answer came from. The answer can still be wrong, so citations and grounding instructions are not guarantees.

Fine-tuning trains a base model on examples so its parameters adapt to a desired style, format, or task behavior. It is useful when a model needs to respond consistently in a specialized way across many requests. It is a weaker fit for storing a changing collection of factual talks: the training set must be curated, updates require another training cycle, and model weights do not provide a dependable citation lookup. RAG was chosen here because talks are source documents to retrieve and cite. A larger system could use both: fine-tune response style while retrieving current talk passages for factual content. See the [OpenAI fine-tuning guide](https://platform.openai.com/docs/guides/fine-tuning) and [Supabase vector search guide](https://supabase.com/docs/guides/ai).

### 5. AI-assisted development — personal draft

> Draft based on this build session; revise it to reflect what you personally found useful or challenging.
>
> I used an AI coding assistant to inspect the assignment steps and starter code, then connect the frontend, SQL schema, data pipeline, and Edge Functions. It helped identify integration issues such as the search function not returning the talk URL and the RAG flow needing an explicit empty-results state. I still had to make product choices, review how filters and RLS fit together, and supply the correct project configuration. I learned that an AI assistant can speed up implementation, but its output still needs to be checked against the actual schema, deployment environment, and security rules.

## Completion evidence

The repository and Pages deployment are available above. A working RAG screenshot requires a configured Supabase project, imported talk data, an OpenAI API key, and deployed functions; add the screenshot after those runtime steps are complete.

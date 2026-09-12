# Docker

This is a portfolio/demo container setup. Docker Compose is not presented as
enterprise production orchestration.

## Build the image

```bash
docker build -t ai-knowledge-agent .
```

The multi-stage build compiles the React frontend first, then copies only the
public application source and frontend build into a slim Python runtime image.
Secrets and private local data are supplied at runtime or excluded from the
build context.

## Run the local demo

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Set non-empty local values for:

   - `OPENAI_API_KEY`
   - `SESSION_SECRET`
   - `ADMIN_PASSWORD`
   - `EMPLOYEE_PASSWORD`

3. Start the app and pgvector database:

   ```bash
   docker compose up --build
   ```

4. Open the app:

   ```text
   http://localhost:8000
   ```

5. Check health without calling OpenAI:

   ```text
   http://localhost:8000/health
   ```

The Compose database uses local demo-only defaults unless `POSTGRES_DB`,
`POSTGRES_USER`, or `POSTGRES_PASSWORD` are overridden. PostgreSQL is not
mapped to the host; the app reaches it through the Compose network.

## Database setup

The app does not automatically run schema setup or ingestion during startup.
After the database is running, run the explicit setup command from a separate
shell:

```bash
docker compose exec app python db_setup.py
```

`db_setup.py` creates the pgvector extension and a basic local table. The
vector ingestion workflow requires the fuller schema and runtime credentials;
review the ingestion script before using it for a deliberate demo setup.

## Fictional sample knowledge

The public sample is at:

```text
examples/sample_knowledge.txt
```

The extraction and chunking utilities use this file by default. They support a
private local source through `KNOWLEDGE_SOURCE_PATH`, but private company
documents are intentionally excluded from the image and Docker build context.

Embedding ingestion requires `OPENAI_API_KEY` and a working `DATABASE_URL`.
It is never run automatically during image build, container startup, or
offline verification.

## Local versus production

For local HTTP Docker testing, use:

```text
APP_ENV=development
```

Production mode enables HTTPS-only session cookies. Actual production use
requires:

- `APP_ENV=production`
- HTTPS termination
- Strong runtime secrets
- A production database and operational backup strategy
- Separate review of the protected-action integration boundary

## Stop and reset

Stop the services while keeping the demo database volume:

```bash
docker compose down
```

Remove the demo database volume only when intentionally resetting local data:

```bash
docker compose down -v
```
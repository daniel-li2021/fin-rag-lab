CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS sources (
 source_id uuid PRIMARY KEY, owner_id text NOT NULL, kind text NOT NULL
 CHECK (kind IN ('pdf','text','markdown','url')), title text NOT NULL,
 locator text, metadata jsonb NOT NULL DEFAULT '{}', metadata_revision int NOT NULL DEFAULT 0, request_key text, registration_hash text,
 status text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','pending','ready','failed','archived')),
 active_version_id uuid, active_build_id uuid, desired_build_id uuid, last_error text,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,request_key)
);
CREATE TABLE IF NOT EXISTS source_versions (
 version_id uuid PRIMARY KEY, source_id uuid NOT NULL REFERENCES sources,
 number int NOT NULL CHECK (number>0), sha256 text NOT NULL CHECK (length(sha256)=64),
 object_key text NOT NULL, media_type text NOT NULL, size_bytes bigint NOT NULL CHECK(size_bytes>0),
 metadata jsonb NOT NULL, provenance jsonb NOT NULL DEFAULT '{}', supersedes_version_id uuid REFERENCES source_versions,
 active_build_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_id,number), UNIQUE(source_id,sha256), UNIQUE(source_id,version_id)
);
CREATE TABLE IF NOT EXISTS retrieval_builds (
 build_id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES source_versions,
 config_hash text NOT NULL, manifest jsonb NOT NULL, status text NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','ready','failed')), UNIQUE(version_id,config_hash), UNIQUE(version_id,build_id)
);
CREATE TABLE IF NOT EXISTS ingestion_jobs (
 job_id uuid PRIMARY KEY, build_id uuid NOT NULL UNIQUE REFERENCES retrieval_builds,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','ready','failed')),
 lease_token uuid, lease_until timestamptz, attempts int NOT NULL DEFAULT 0,
 error text, usage jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS blocks (
 build_id uuid NOT NULL REFERENCES retrieval_builds, block_id text NOT NULL,
 ordinal int NOT NULL, payload jsonb NOT NULL, PRIMARY KEY(build_id,block_id)
);
CREATE TABLE IF NOT EXISTS chunks (
 build_id uuid NOT NULL REFERENCES retrieval_builds, chunk_id text NOT NULL,
 parent_id text, ordinal int NOT NULL, payload jsonb NOT NULL,
 retrieval_text text NOT NULL, input_hash text NOT NULL,
 lexical tsvector GENERATED ALWAYS AS (to_tsvector('simple',retrieval_text)) STORED,
 PRIMARY KEY(build_id,chunk_id),
 FOREIGN KEY(build_id,parent_id) REFERENCES chunks(build_id,chunk_id)
);
CREATE INDEX IF NOT EXISTS chunks_lexical ON chunks USING gin(lexical);
CREATE TABLE IF NOT EXISTS chunk_embeddings (
 build_id uuid NOT NULL, chunk_id text NOT NULL, model text NOT NULL,
 dimensions int NOT NULL CHECK(dimensions>0), input_hash text NOT NULL,
 embedding vector NOT NULL CHECK(vector_dims(embedding)=dimensions),
 PRIMARY KEY(build_id,chunk_id), FOREIGN KEY(build_id,chunk_id) REFERENCES chunks
);
CREATE TABLE IF NOT EXISTS metadata_suggestions (
 version_id uuid NOT NULL REFERENCES source_versions, cache_key text NOT NULL,
 payload jsonb NOT NULL, usage jsonb, PRIMARY KEY(version_id,cache_key)
);
-- Append-only corrections; raw source versions and previous research remain intact.
CREATE TABLE IF NOT EXISTS source_version_metadata_reviews (
 review_id uuid PRIMARY KEY, version_id uuid NOT NULL REFERENCES source_versions,
 revision int NOT NULL CHECK(revision>0), metadata jsonb NOT NULL,
 reviewer text NOT NULL, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(version_id,revision)
);
CREATE TABLE IF NOT EXISTS financial_observations (
 owner_id text NOT NULL, observation_id text NOT NULL, build_id uuid NOT NULL REFERENCES retrieval_builds,
 payload jsonb NOT NULL, payload_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(owner_id,observation_id)
);
CREATE TABLE IF NOT EXISTS research_collections (
 collection_id uuid PRIMARY KEY, owner_id text NOT NULL, name text NOT NULL,
 kind text NOT NULL CHECK(kind IN ('collection','watchlist')), source_ids jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(owner_id,name)
);
CREATE TABLE IF NOT EXISTS research_runs (
 owner_id text NOT NULL, run_id text NOT NULL, payload jsonb NOT NULL,
 collection_id uuid REFERENCES research_collections, parent_run_id text,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(owner_id,run_id),
 FOREIGN KEY(owner_id,parent_run_id) REFERENCES research_runs(owner_id,run_id)
);
ALTER TABLE sources ADD COLUMN IF NOT EXISTS metadata_revision int NOT NULL DEFAULT 0;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS registration_hash text;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS desired_build_id uuid;
ALTER TABLE source_versions ADD COLUMN IF NOT EXISTS active_build_id uuid;
ALTER TABLE blocks ADD COLUMN IF NOT EXISTS ordinal int NOT NULL DEFAULT 0;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='sources_active_version_fk') THEN
  ALTER TABLE sources ADD CONSTRAINT sources_active_version_fk
   FOREIGN KEY(source_id,active_version_id) REFERENCES source_versions(source_id,version_id);
  ALTER TABLE sources ADD CONSTRAINT sources_active_build_fk
   FOREIGN KEY(active_version_id,active_build_id) REFERENCES retrieval_builds(version_id,build_id);
 END IF;
END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='versions_active_build_fk') THEN
  ALTER TABLE source_versions ADD CONSTRAINT versions_active_build_fk
   FOREIGN KEY(version_id,active_build_id) REFERENCES retrieval_builds(version_id,build_id);
 END IF;
END $$;

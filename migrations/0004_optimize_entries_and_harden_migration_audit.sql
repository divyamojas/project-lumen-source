DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'entries_title_trimmed_chk'
      AND conrelid = 'public.entries'::regclass
  ) THEN
    ALTER TABLE public.entries
      ADD CONSTRAINT entries_title_trimmed_chk
      CHECK (char_length(btrim(title)) BETWEEN 1 AND 100);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'entries_body_non_empty_chk'
      AND conrelid = 'public.entries'::regclass
  ) THEN
    ALTER TABLE public.entries
      ADD CONSTRAINT entries_body_non_empty_chk
      CHECK (char_length(btrim(body)) > 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'entries_updated_after_created_chk'
      AND conrelid = 'public.entries'::regclass
  ) THEN
    ALTER TABLE public.entries
      ADD CONSTRAINT entries_updated_after_created_chk
      CHECK ("updatedAt" >= "createdAt");
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS entries_user_favorite_created_idx
  ON public.entries (user_id, favorite, "createdAt" DESC);

CREATE INDEX IF NOT EXISTS entries_user_pinned_created_idx
  ON public.entries (user_id, pinned, "createdAt" DESC);

CREATE INDEX IF NOT EXISTS entries_user_collection_created_idx
  ON public.entries (user_id, collection, "createdAt" DESC);

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'schema_migrations'
      AND column_name = 'applied_by'
      AND udt_name = 'text'
  ) THEN
    ALTER TABLE public.schema_migrations
      ALTER COLUMN applied_by TYPE uuid
      USING NULLIF(applied_by, '')::uuid;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS schema_migrations_applied_by_idx
  ON public.schema_migrations (applied_by);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'schema_migrations_applied_by_fkey'
      AND conrelid = 'public.schema_migrations'::regclass
  ) THEN
    ALTER TABLE public.schema_migrations
      ADD CONSTRAINT schema_migrations_applied_by_fkey
      FOREIGN KEY (applied_by) REFERENCES auth.users(id) ON DELETE SET NULL;
  END IF;
END $$;

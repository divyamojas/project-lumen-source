-- Migration: add journal_type support
-- Adds journal_type to entries table and user_preferences table

ALTER TABLE entries
  ADD COLUMN IF NOT EXISTS journal_type VARCHAR(32) DEFAULT 'personal',
  ADD COLUMN IF NOT EXISTS type_metadata JSONB DEFAULT '{}';

DO $$
BEGIN
  IF EXISTS (
    SELECT
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'users'
  ) THEN
    ALTER TABLE public.users
      ADD COLUMN IF NOT EXISTS default_journal_type VARCHAR(32) DEFAULT 'personal',
      ADD COLUMN IF NOT EXISTS enabled_journal_types JSONB DEFAULT '["personal"]';
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_entries_journal_type ON entries(journal_type);

COMMENT ON COLUMN entries.journal_type IS
  'One of: personal, science, travel, fitness, work, creative';
COMMENT ON COLUMN entries.type_metadata IS
  'Freeform JSON for type-specific fields. Schema varies by journal_type.';
DO $$
BEGIN
  IF EXISTS (
    SELECT
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'enabled_journal_types'
  ) THEN
    COMMENT ON COLUMN public.users.enabled_journal_types IS
      'Array of journal types this user has activated';
  END IF;
END
$$;

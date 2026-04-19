CREATE TABLE IF NOT EXISTS public.sync_audit_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  entry_id text,
  action text NOT NULL,
  status text NOT NULL,
  scope text NOT NULL DEFAULT 'entry',
  bucket text,
  object_key text,
  region text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sync_audit_log_user_created_idx
  ON public.sync_audit_log (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS sync_audit_log_status_idx
  ON public.sync_audit_log (status);

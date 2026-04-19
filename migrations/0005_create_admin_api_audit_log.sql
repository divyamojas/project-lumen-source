CREATE TABLE IF NOT EXISTS public.admin_api_audit_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  executed_by  uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  action       text NOT NULL,
  target       text NOT NULL,
  request_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  row_count    integer,
  status       text NOT NULL DEFAULT 'success',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS admin_api_audit_log_executed_by_idx
  ON public.admin_api_audit_log (executed_by);

CREATE INDEX IF NOT EXISTS admin_api_audit_log_created_at_idx
  ON public.admin_api_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS admin_api_audit_log_action_idx
  ON public.admin_api_audit_log (action);

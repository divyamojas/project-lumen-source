create table if not exists sql_audit_log (
  id          uuid primary key default gen_random_uuid(),
  executed_by uuid references auth.users(id),
  query       text not null,
  status      text,
  row_count   integer,
  duration_ms integer,
  executed_at timestamptz not null default now()
);

create index if not exists sql_audit_log_executed_by_idx on sql_audit_log(executed_by);
create index if not exists sql_audit_log_executed_at_idx on sql_audit_log(executed_at desc);

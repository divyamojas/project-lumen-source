create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  enabled_journal_types jsonb not null default '["personal"]',
  default_journal_type varchar(32) not null default 'personal'
);

comment on column public.users.enabled_journal_types is
  'Array of journal types this user has activated';

comment on column public.users.default_journal_type is
  'Default journal type selected for new entries.';

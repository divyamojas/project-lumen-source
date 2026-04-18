create table if not exists entries (
  id                text primary key,
  user_id           uuid not null references auth.users(id) on delete cascade,
  title             text not null,
  body              text not null,
  "createdAt"       timestamptz not null,
  "updatedAt"       timestamptz not null,
  "accentColor"     jsonb not null default '{}',
  theme             text not null default 'neutral',
  tags              text[] not null default '{}',
  favorite          boolean not null default false,
  pinned            boolean not null default false,
  collection        text not null default '',
  checklist         jsonb not null default '[]',
  "templateId"      text not null default '',
  "promptId"        text not null default '',
  "relatedEntryIds" text[] not null default '{}'
);

create index if not exists entries_user_id_idx         on entries(user_id);
create index if not exists entries_created_at_idx      on entries("createdAt" desc);
create index if not exists entries_user_created_idx    on entries(user_id, "createdAt" desc);
create index if not exists entries_tags_gin_idx        on entries using gin(tags);
create index if not exists entries_collection_idx      on entries(user_id, collection);

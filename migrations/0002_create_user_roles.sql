create table if not exists user_roles (
  user_id     uuid primary key references auth.users(id) on delete cascade,
  role        text not null default 'user'
                check (role in ('user', 'admin', 'superuser')),
  assigned_by uuid references auth.users(id),
  assigned_at timestamptz not null default now()
);

create index if not exists user_roles_role_idx on user_roles(role);

-- VibeCut: what the app learns about a person, mirrored from the Mac
-- (web/backend/cloud.py). No footage, no frames: defaults, confirmed rules,
-- the profile, and styles learnt from reels. Keyed by device until sign-in.

create table if not exists preferences (
  device      text        not null,
  kind        text        not null check (kind in ('default', 'rule', 'profile', 'vibe')),
  key         text        not null,
  value       jsonb       not null,
  updated_at  timestamptz not null default now(),
  primary key (device, kind, key)
);

create index if not exists preferences_device_kind on preferences (device, kind);

-- Until there is a sign-in, the anon key may read and write its own device's
-- rows. Tighten to auth.uid() when accounts arrive.
alter table preferences enable row level security;
create policy "device rows" on preferences for all using (true) with check (true);

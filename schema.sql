-- Jalankan sekali di Supabase: menu SQL Editor > New query > tempel semua isi file ini > Run.
-- Membuat tabel, bucket penyimpanan file, dan 5 akun awal (user1 s.d. user5, password 123456).

create table if not exists public.app_users (
  id bigint generated always as identity primary key,
  username text unique not null,
  password_hash text not null,
  created_at timestamptz default now()
);

create table if not exists public.datasets (
  id text primary key,
  user_id bigint references public.app_users(id) on delete cascade,
  name text not null,
  filename text,
  sheet text,
  storage_path text,
  info jsonb,
  labels jsonb,
  created_at timestamptz default now()
);

create table if not exists public.runs (
  id text primary key,
  user_id bigint references public.app_users(id) on delete cascade,
  dataset_id text references public.datasets(id) on delete set null,
  name text,
  note text,
  settings jsonb,
  summary jsonb,
  status text,
  excel_path text,
  charts_path text,
  created_at timestamptz default now()
);

create index if not exists runs_user_idx on public.runs(user_id, created_at desc);
create index if not exists datasets_user_idx on public.datasets(user_id, created_at desc);

-- RLS aktif tanpa policy: tabel tidak bisa diakses dengan anon key dari luar.
-- Aplikasi memakai service_role key (disimpan di Secrets Streamlit, tidak pernah dikirim ke browser).
alter table public.app_users enable row level security;
alter table public.datasets enable row level security;
alter table public.runs enable row level security;

-- Bucket privat untuk file Excel upload dan hasil run.
insert into storage.buckets (id, name, public)
values ('proyeksi-files', 'proyeksi-files', false)
on conflict (id) do nothing;

-- 5 akun awal. Password 123456 disimpan sebagai hash PBKDF2, bukan teks asli.
insert into public.app_users (username, password_hash) values
  ('user1', 'pbkdf2$120000$e821ae2928dd53dabb1196e4efb33aab$2989d80deff8f10fa2042f91c571187ae71526c28e809becba033e02359cbc45'),
  ('user2', 'pbkdf2$120000$932a4c7086b79421f01b053bd2a1ca3d$1410d1b0eb21ed8f3c74b39f667c5a7e3494bd19444ecab25d1286589cc012f4'),
  ('user3', 'pbkdf2$120000$09310d60f70be280c105b686303e8529$66a7871427ef5e729effe5c637725b166e99522ef92215b0a781ffcc29b7137a'),
  ('user4', 'pbkdf2$120000$17c3c3d24c39799129c7af0d5c2acaaf$a57cf810398d6fb23a87096704f81b91902c762f7fcc1af6e4aeccf5bb0c2019'),
  ('user5', 'pbkdf2$120000$0cb025afc3d6d9f16fed04547a6d5caf$717e7bea1aa655e5ecbb8ed21d7df86222e982a877a1add0e03664a9ebe33272')
on conflict (username) do nothing;

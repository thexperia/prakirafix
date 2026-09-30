-- Jalankan sekali di Supabase: menu SQL Editor > New query > tempel semua isi file ini > Run.
-- Membuat tabel, bucket penyimpanan file, dan 5 akun awal (password awal 123456).

create table if not exists public.app_users (
  id bigint generated always as identity primary key,
  username text unique not null,
  password_hash text not null,
  display_name text,
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
insert into public.app_users (username, display_name, password_hash) values
  ('rachmad', 'Rachmad Irvan Syahputra', 'pbkdf2$120000$ad953f56281002358c97916e529cc500$da37327e654d3fff092cfae9fe2b7a9a7702e8dfae821baa0892a1b4f4c9c82c'),
  ('febiola', 'Febiola Napitupulu', 'pbkdf2$120000$9ca0e4612ac22f215013c455cc0814eb$34f8820437f20793a66521320c1b729d094be2b4b482489f1c796f425b58275f'),
  ('torkis', 'Torkis Justicio Paruhum Natigor Hasibuan', 'pbkdf2$120000$f6c59cef5b658b589d007127ae21ba27$de2c780a5cd91f1306235cf46c58d1229485e44921663f6857ff2241b0a3b2dd'),
  ('shania', 'Shania Gumilar', 'pbkdf2$120000$2d9d5be6ba6dd488b23451c5bfaf7d15$dbe36121622370a87452e7f0ed9585ccfb8a8d80fa27f39e645b3a320616536f'),
  ('sigit', 'Sigit Setiawan', 'pbkdf2$120000$301b89c1ab9a3216c936773a11d44d0a$87ea0dd26e56ccd180732049cff18cbdffa7c37a9d297f5998b330b00a38094c')
on conflict (username) do nothing;

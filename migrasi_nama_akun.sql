-- MIGRASI untuk project Supabase yang SUDAH menjalankan schema.sql versi lama (akun user1 s.d. user5).
-- Jalankan sekali di SQL Editor. Data dan riwayat run tiap akun tetap aman (hanya nama akun yang berubah).
alter table public.app_users add column if not exists display_name text;

update public.app_users set username = 'rachmad', display_name = 'Rachmad Irvan Syahputra' where username = 'user1';
update public.app_users set username = 'febiola', display_name = 'Febiola Napitupulu' where username = 'user2';
update public.app_users set username = 'torkis',  display_name = 'Torkis Justicio Paruhum Natigor Hasibuan' where username = 'user3';
update public.app_users set username = 'shania',  display_name = 'Shania Gumilar' where username = 'user4';
update public.app_users set username = 'sigit',   display_name = 'Sigit Setiawan' where username = 'user5';

select id, username, display_name from public.app_users order by id;

# Proyeksi PDRB: Web App Forecasting Indikator Regional

Aplikasi web (Streamlit) untuk memproyeksi pertumbuhan PDRB dengan 14 metode + Ensemble.
Logika proyeksi sama persis dengan notebook Colab (`core/proyeksi_pdrb.py`).

## Fitur
- Login 5 akun (`rachmad`, `febiola`, `torkis`, `shania`, `sigit`; password awal `123456`), bisa ganti password di menu Akun
- Unduh template Excel, unggah data, validasi format (error + peringatan dengan lokasi sel), pratinjau data
- Dataset tersimpan per akun, bisa dipakai lagi di sesi berikutnya
- Pilih target, kolom level (opsional), periode, indikator (lengkap dengan korelasi), metode, add-factor
- Detail run lengkap seperti Excel Colab + unduh Excel dan grafik; satu grafik semua metode dengan pilihan metode yang disorot, plus rangkuman model
- Pengaturan penanda pandemi (bulan), outlier per indikator (dipilih sendiri), Ramadan/Lebaran/Idul Adha (H- dan H+), batas lompatan on/off, dan mode advanced per metode
- Impor hasil run dari Google Colab (.zip) langsung ke riwayat, tanpa run ulang
- Beranda berisi dashboard dan riwayat run; tooltip ⓘ dan halaman Glosarium untuk semua istilah

## Struktur
```
app.py                 login + navigasi
views/                 halaman: beranda, data, jalankan, riwayat (detail run), glosarium, akun
core/proyeksi_pdrb.py  mesin proyeksi (sama dengan notebook)
core/engine.py         menjalankan mesin dengan pengaturan dari aplikasi
core/validasi.py       pemeriksa file upload
core/template.py       pembuat template Excel
core/storage.py        penyimpanan: Supabase (deploy) atau lokal (uji coba)
core/auth.py           login (password di-hash PBKDF2)
core/glosarium.json    teks penjelasan istilah
schema.sql             tabel + bucket + 5 akun untuk Supabase (project baru)
migrasi_nama_akun.sql  ganti user1-user5 ke nama baru (project yang sudah jalan)
```

## Coba di laptop (opsional)
```
pip install -r requirements.txt
streamlit run app.py
```
Tanpa pengaturan Supabase, aplikasi otomatis memakai penyimpanan lokal (folder `local_data/`).

---

## Langkah deploy

### A. Supabase (database + penyimpanan file)
1. Masuk ke https://supabase.com lalu **New project**. Isi nama, buat password database (simpan), region **Southeast Asia (Singapore)**. Tunggu sampai project siap.
2. Menu kiri **SQL Editor** lalu **New query**. Buka file `schema.sql`, salin semua isinya, tempel, klik **Run**. Harus muncul "Success".
3. Cek: menu **Table Editor** berisi tabel `app_users` (5 baris), `datasets`, `runs`. Menu **Storage** berisi bucket `proyeksi-files`.
4. Menu **Project Settings** lalu **API** (atau **API Keys**). Salin:
   - **Project URL** (contoh `https://abcd1234.supabase.co`)
   - **service_role** key (klik Reveal). Key ini rahasia: jangan ditaruh di kode atau dibagikan.

### B. GitHub
1. Buat repository baru, sebaiknya **Private**, misalnya `proyeksi-pdrb-app`.
2. **Add file** lalu **Upload files**: unggah SEMUA isi folder ini (termasuk folder `core`, `views`, `.streamlit`), kecuali `local_data`. Commit.
   - Folder `.streamlit` diawali titik; bila tidak ikut terunggah, buat manual file `.streamlit/config.toml` lewat **Add file** lalu **Create new file** dan tempel isinya.

### C. Streamlit Community Cloud
1. Masuk ke https://share.streamlit.io dengan akun GitHub. Izinkan akses ke repo private bila diminta.
2. **Create app** lalu **Deploy a public app from GitHub**. Pilih repo, branch `main`, main file `app.py`. Atur App URL sesuai selera.
3. Klik **Advanced settings**: Python version 3.11 atau 3.12. Di kotak **Secrets** tempel (ganti isinya):
   ```
   [supabase]
   url = "https://abcd1234.supabase.co"
   key = "service_role key dari langkah A.4"
   ```
4. Klik **Deploy**. Instalasi pertama sekitar 3 s.d. 5 menit.
5. Buka link aplikasi. Di bawah form login harus tertulis **"Penyimpanan: Supabase"**. Bila tertulis "lokal", cek lagi isi Secrets.

### D. Uji coba
1. Login `rachmad` / `123456`
2. Menu Data: unduh template, unggah file dengan format salah, pastikan pesan error muncul
3. Unggah file data yang benar, cek pratinjau, simpan
4. Jalankan Proyeksi (mode lengkap sekitar 2 menit), cek hasil sama dengan Colab
5. Keluar, login lagi: dataset dan riwayat harus masih ada
6. Login `febiola`: tidak boleh melihat data rachmad

### E. Memasukkan hasil run Colab yang sudah ada (tanpa run ulang)
1. Login sebagai akun tujuan (mis. `rachmad`).
2. Menu **Riwayat Run** lalu buka **Impor hasil run dari Google Colab (.zip)**.
3. Unggah zip hasil Colab (berisi `hasil_proyeksi.xlsx` + grafik PNG; bila ada file data seperti `Indikator_Makroekonomi_DIY.xlsx`, ikut tersimpan sebagai dataset).
4. Periksa ringkasan yang terbaca, ubah nama run bila perlu, klik **Simpan ke riwayat**.

### F. Update dari versi sebelumnya (akun user1 s.d. user5 sudah ada)
1. Supabase: **SQL Editor** lalu **New query**, tempel isi `migrasi_nama_akun.sql`, klik **Run**. Akun user1 s.d. user5 berganti nama menjadi rachmad, febiola, torkis, shania, sigit. Dataset dan riwayat run tetap ada karena id akun tidak berubah (run impor Colab milik user1 menjadi milik rachmad). Password yang sudah diganti lewat menu Akun tidak ikut berubah.
2. GitHub: buka repo, **Add file** lalu **Upload files**, unggah semua isi folder ini (menimpa file lama), Commit. File yang wajib ikut: `app.py`, folder `core`, folder `views`.
3. Streamlit Cloud memperbarui otomatis dalam 1 s.d. 2 menit. Bila tampilan belum berubah, buka menu **⋮** di app lalu **Reboot app**.

## Perlu diingat
- Streamlit gratis tidur setelah 12 jam tanpa pengunjung; klik tombol untuk membangunkan.
- Supabase gratis di-pause setelah 1 minggu tidak dipakai. Buka dashboard Supabase sebelum presentasi.
- Beberapa user yang menjalankan proyeksi bersamaan berbagi CPU gratis, jadi bisa lebih lambat. Pakai **Mode cepat** untuk coba-coba.
- Ini prototype: password sederhana. Ganti password lewat menu Akun sebelum dipakai lebih luas.
- Mengubah aplikasi: ganti file di GitHub, Streamlit otomatis memperbarui dalam 1 s.d. 2 menit.

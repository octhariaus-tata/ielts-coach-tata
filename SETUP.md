# Setup sekali pada setiap laptop

Panduan ini untuk Suk atau coach. Tata memakai chat setelah setup selesai. Semua referensi file memakai lokasi relatif terhadap folder project, sehingga folder dapat berada di lokasi berbeda pada macOS, Windows atau Linux.

## 1. Periksa perangkat dan akses

- Pastikan Codex tersedia dan pengguna dapat login pada akun yang dipakai belajar. Jangan mengubah pengaturan akun atau permissions.
- Periksa Git dengan `git --version`.
- Periksa Python 3.8 atau lebih baru dengan `python3 --version`. Pada Windows, gunakan `py -3 --version` jika `python3` tidak tersedia; `python --version` hanya boleh dipakai setelah dipastikan versinya memenuhi. Gunakan interpreter yang sama untuk seluruh perintah berikutnya.
- Jika prasyarat belum tersedia, laporkan yang kurang. Jangan memasang software secara diam-diam.
- Pastikan akses GitHub pada akun yang berhak mengakses repo privat `octhariaus-tata/ielts-coach-tata`. Credential GitHub lokal perlu diperiksa terpisah dari login Codex. Gunakan cara autentikasi GitHub yang tersedia; jangan menyimpan token/password dalam repo, URL remote, catatan sesi atau chat.

Script menggunakan pustaka standar Python dan perintah Git. GitHub connector yang terhubung dapat memakai akun berbeda dari browser atau Git lokal; jangan menganggap akses ketiganya sama. Jangan menambahkan collaborator atau mengganti konektor sebagai cara mengatasi akses tanpa arahan pengguna.

## 2. Ambil salinan utama

Untuk laptop baru, clone ke lokasi yang dipilih Suk:

```sh
git clone https://github.com/octhariaus-tata/ielts-coach-tata.git
cd ielts-coach-tata
git branch --show-current
git remote -v
```

Branch harus `main` dan remote harus repo privat yang diizinkan. Jangan mengubah remote untuk membuat setup lolos. Jika ada salinan ZIP/folder lama, pertahankan sampai isi dan bukti dibandingkan dengan repo; jangan menimpa histori secara diam-diam.

Pada komputer asal, repo mungkin sedang disiapkan oleh coach. Periksa `STATUS.md` dan keberadaan remote terlebih dahulu; jangan menganggap publikasi selesai sebelum push dan akses repo terverifikasi.

Tambahkan folder hasil clone sebagai local project di Codex. Buka chat di project itu dan gunakan prompt awal di `README.md`. Coach membaca `AGENTS.md` dari folder project; instruksi project tidak dipindahkan lewat login akun saja. [Project OpenAI](https://learn.chatgpt.com/docs/projects), [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## 3. Periksa alat dan versi

Dari folder repo, buka bantuan script:

```sh
python3 scripts/sync.py --help
python3 scripts/session.py --help
```

Di Windows, ganti awalan `python3` dengan `py -3` bila itu interpreter yang sudah diperiksa. Coach menggunakan:

```sh
python3 scripts/sync.py status
python3 scripts/sync.py pull
python3 scripts/sync.py push --message "Simpan sesi IELTS"
```

Sinkronisasi memeriksa remote aktual. Nyatakan tersinkron hanya bila hasil menunjukkan `status: synced` serta `remote_verified: true`; exit code nol sendiri belum cukup karena repo tanpa remote dapat berstatus `unpublished`. Informasi pemeriksaan lokal tersimpan dalam `.local/sync.json` yang tidak ikut Git.

Alat sesi memakai ID materi yang dipilih coach dari `materials.json`:

```sh
python3 scripts/session.py start --task TASK_ID --skill Listening --kind pilot --minutes 20
python3 scripts/session.py status
python3 scripts/session.py finalize --id SESSION_ID --result .local/result.json
python3 scripts/session.py rebuild
```

`TASK_ID` dan `SESSION_ID` adalah placeholder yang harus diganti dengan nilai yang tersedia; perintah ini tidak menjalankan audio atau latihan. Coach menyiapkan JSON hasil sesuai [panduan alat sesi](scripts/README.md). Sesi yang belum cukup bukti tetap aktif; jangan memanggil `finalize` untuk mengarang kelengkapannya. `start` dan “done” berulang memakai record yang sudah ada. `rebuild` memperbarui hanya bagian ringkasan yang dikelola script dalam `PROGRESS.md` dan `STATUS.md`, mempertahankan riwayat lama dan catatan kesiapan manual.

Sebelum sesi, coach memeriksa Git lalu mengambil versi terbaru secara aman. Jika perubahan lokal atau versi bercabang menghalangi pull, simpan seluruh record/bukti dan rekonsiliasi dulu. Jangan menjalankan reset atau force-push. Ringkasan baru dapat dibangun kembali dari record sesi; riwayat lama tetap dipertahankan.

## 4. Uji kesiapan laptop yang akan dipakai

Kirim **“Kesiapan”** di chat dan minta coach melakukan pemeriksaan berikut:

1. Baca profil, plan, progres dan status dari salinan terbaru; pastikan tidak ada dua laptop menjalankan sesi aktif bersamaan.
2. Pastikan file dapat disimpan lalu dibaca ulang. Gunakan data tes sistem yang terpisah dari kemajuan Tata.
3. Uji satu perubahan tes sistem tersinkron dan terlihat pada salinan kedua, lalu bersihkan data tes dari alur belajar. Jangan mengklaim uji lintas laptop bila kedua salinan masih berada pada satu komputer.
4. Periksa link tugas pertama, jenis soal, key dan transcript/audio jika relevan. Akses browser dan hasil harus diuji di laptop ini. Jangan memulai rekaman satu kali putar untuk Tata.
5. Pastikan screenshot nomor soal/jawaban dapat dikirim dan bukti yang tersedia dapat disimpan. Rekaman Speaking diuji sebelum digunakan; transcript saja tidak cukup untuk menilai pronunciation.
6. Catat hasil pemeriksaan dan yang masih belum diuji di `STATUS.md`, lalu sinkronkan.

Setelah pemeriksaan berhasil, Tata cukup mengatakan **“Mulai”**. Laptop Tata belum diuji sampai pemeriksaan pada perangkat itu benar-benar dilakukan.

## Jika koneksi terputus

Coach menyimpan hasil pada laptop yang sama, membaca ulang, dan menandai **belum tersinkron**. Lanjutkan attempt dengan **“Lanjut”** pada perangkat itu. Saat koneksi kembali, coach menyinkronkan dan memastikan push berhasil sebelum Tata pindah laptop. Jika akses GitHub ditolak, jelaskan kendala autentikasi atau izin yang benar-benar terlihat; jangan menganggap akun Codex memberi akses GitHub otomatis.

Jangan mengedit folder mirror `.codex/.chatgpt-projects/`, sumber sinkron lain, pengaturan akun atau permissions. Jangan memasang layanan, membuat automasi atau mengirim pesan sebagai bagian setup ini.

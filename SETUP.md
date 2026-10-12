# Setup sekali pada setiap laptop

Panduan ini untuk Suk atau coach. Tata memakai chat setelah setup selesai. Semua referensi file memakai lokasi relatif terhadap folder project, sehingga folder dapat berada di lokasi berbeda pada macOS, Windows atau Linux.

## 1. Periksa perangkat dan akses

- Pastikan Codex tersedia dan pengguna dapat login pada akun yang dipakai belajar. Jangan mengubah pengaturan akun atau permissions.
- Periksa Git dengan `git --version`.
- Periksa Python 3.8 atau lebih baru dengan `python3 --version`. Pada Windows, gunakan `py -3 --version` jika `python3` tidak tersedia; `python --version` hanya boleh dipakai setelah dipastikan versinya memenuhi. Gunakan interpreter yang sama untuk seluruh perintah berikutnya.
- Jika prasyarat belum tersedia, laporkan yang kurang. Jangan memasang software secara diam-diam.
- Pastikan akses GitHub pada akun yang berhak mengakses repo privat `octhariaus-tata/ielts-coach-tata`. Credential GitHub lokal perlu diperiksa terpisah dari login Codex. Gunakan cara autentikasi GitHub yang tersedia; jangan menyimpan token/password dalam repo, URL remote, catatan sesi atau chat.

Script menggunakan pustaka standar Python dan perintah Git. GitHub connector yang terhubung dapat memakai akun berbeda dari browser atau Git lokal; jangan menganggap akses ketiganya sama. Jangan menambahkan collaborator atau mengganti konektor sebagai cara mengatasi akses tanpa arahan pengguna.

Di komputer asal, pengguna telah mengizinkan GitHub CLI resmi lokal di `.local/bin/gh` dan menyelesaikan login octhariaus-tata. Helper Git disetel hanya pada repo lokal, tanpa mengubah Git global. Folder `.local/` dan credential tidak ikut clone. Pada laptop baru, Suk perlu menyiapkan autentikasi Git yang tersedia; jika memakai CLI tambahan, mintalah izin pemasangan dan biarkan pengguna menyelesaikan otorisasi. Jangan menyalin credential dari komputer asal.

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

Dua skill project berada di `.agents/skills/ielts-coach/SKILL.md` dan `.agents/skills/ielts-github-sync/SKILL.md`, dengan metadata opsional `agents/openai.yaml` masing-masing. Skill ikut repo dan merujuk aturan/alat lokal; tidak perlu menyalin ke folder skill pribadi atau mengubah pengaturan akun. Periksa keduanya pada project/laptop ini; keberadaan file tidak membuktikan katalog aplikasi saat itu telah memuatnya. Jika tidak ditemukan, laporkan dan gunakan AGENTS serta CLI yang tersedia sambil memperbaiki pemeriksaan discovery. Lokasi repo-local tersebut didukung [panduan skills OpenAI](https://learn.chatgpt.com/docs/build-skills).

## 3. Periksa alat dan versi

Dari folder repo, buka bantuan script:

```sh
python3 scripts/sync.py --help
python3 scripts/session.py --help
python3 scripts/coach.py --help
python3 scripts/coach.py prepare --help
python3 scripts/coach.py checkpoint --help
python3 scripts/coach.py complete --help
python3 scripts/coach.py status --help
python3 scripts/coach.py feedback --help
python3 scripts/adaptation.py --help
python3 scripts/hourly_sync.py --help
```

Di Windows, ganti awalan `python3` dengan `py -3` bila itu interpreter yang sudah diperiksa. Coach menggunakan:

```sh
python3 scripts/sync.py status
python3 scripts/sync.py pull
python3 scripts/sync.py push --message "Simpan sesi IELTS"
```

Sinkronisasi memeriksa remote aktual. Nyatakan tersinkron hanya bila hasil menunjukkan `status: synced` serta `remote_verified: true`; exit code nol sendiri belum cukup karena repo tanpa remote dapat berstatus `unpublished`. Informasi pemeriksaan lokal tersimpan dalam `.local/sync.json` yang tidak ikut Git.

Coach memakai operasi wrapper: `prepare` untuk pemeriksaan awal/resume, `checkpoint` untuk respons dan bukti yang baru diterima, `complete` untuk hasil review yang sudah memenuhi syarat, `status` untuk keadaan sesi/kesiapan, dan `feedback` untuk masukan mentah beserta asalnya. `prepare`, `status` dan `complete` juga memberikan konteks adaptasi untuk diperiksa coach. Bentuk argumen dan JSON ada pada bantuan subcommand serta [panduan alat coach](scripts/README.md). ID materi dipilih coach dari `materials.json`; pemilihan tugas dan penilaian tetap dilakukan coach. Perintah ini tidak menjalankan audio atau latihan.

Checkpoint disimpan dan dibaca ulang sebelum penilaian, lengkap dengan asal dan waktu bukti, lalu dicoba sinkronkan. Respons awal dan revisi setelah feedback tetap terpisah. Fase menunggu bukti/review memakai ID semula; skor kosong atau input `unverified` tidak menutup sesi. Jika record tersimpan tetapi ringkasan gagal ditulis, jangan push ringkasan lama: retry memulihkan ringkasan dan menyinkronkan tanpa penilaian ulang. Wrapper memakai modul sesi/sinkronisasi yang tersedia; `scripts/session.py` tetap dapat dipakai untuk operasi dasar, pemeriksaan record dan pemulihan ringkasan. `rebuild` mempertahankan riwayat lama serta catatan kesiapan manual. Record sesi lama tetap terbaca.

Sebelum sesi, coach memeriksa Git lalu mengambil versi terbaru secara aman. Attempt aktif beserta respons lokal tetap dapat dilanjutkan meskipun pull terhalang, dengan batas versi bersama disebutkan. Jika perubahan lokal dan remote lebih baru, atau versi bercabang, simpan seluruh record/bukti dan rekonsiliasi dulu; jangan mengulang push/pull tanpa menangani perbedaan. Jangan menjalankan reset atau force-push. Ringkasan baru dapat dibangun kembali dari record sesi; riwayat lama tetap dipertahankan.

## 4. Uji kesiapan laptop yang akan dipakai

Kirim **“Kesiapan”** di chat dan minta coach melakukan pemeriksaan berikut:

1. Baca profil, plan, progres dan status dari salinan terbaru yang dapat diverifikasi; pastikan tidak ada dua laptop menjalankan sesi aktif bersamaan.
2. Pastikan file dapat disimpan lalu dibaca ulang. Gunakan data tes sistem yang terpisah dari kemajuan Tata.
3. Uji satu perubahan tes sistem tersinkron dan terlihat pada salinan kedua, lalu bersihkan data tes dari alur belajar. Jangan mengklaim uji lintas laptop bila kedua salinan masih berada pada satu komputer.
4. Periksa prompt, jenis soal, audio jika relevan, dan cache key/transcript yang sesuai versi/checksum untuk tugas pertama dan cadangannya. Jangan membagikan `coach_refs/` atau bundled PDF sumber sebelum selesai. Akses browser dan hasil harus diuji di laptop ini. Jangan memulai rekaman satu kali putar untuk Tata.
5. Pastikan screenshot nomor soal/jawaban dapat dikirim dan bukti yang tersedia dapat disimpan. Rekaman Speaking diuji sebelum digunakan; transcript saja tidak cukup untuk menilai pronunciation.
6. Simpan pemeriksaan per perangkat di `.local/readiness.json`: setiap fitur `passed`, `failed`, atau `not_tested`, waktu lokal serta asal bukti. ID perangkat dan lokasi folder mencegah cache dari salinan lain dianggap pemeriksaan laptop ini. Observasi pengguna perlu sumber dan waktu; tes kode/file saja tidak membuktikan playback, pengiriman screenshot, atau rekaman. Ringkas batas pemeriksaan di `STATUS.md` bila perlu; `.local/` tidak ikut Git.

Sesudah kesiapan teknis, periksa kecukupan bukti belajar secara terpisah: perlu diagnostik baru keempat skill dan waktu sesi panjang yang dikonfirmasi. Trial/rehearsal tidak menjadi baseline. Data feedback dan analisis (`feedback/`, `learning/`) ikut repo privat; kesiapan perangkat serta credential tetap lokal. Uji adaptasi dengan data `system_test` tanpa menciptakan preferensi atau progres Tata. [Desain keseluruhan](SYSTEM.md), [aturan adaptasi](ADAPTATION.md).

Laporkan terpisah **siap Listening lokal** (`ready_local_listening`), **kontrol pemutar teruji** (`player_controls_verified`), **Speaking dengan audio terverifikasi** (`speaking_verified`), serta **aman pindah laptop** (`safe_switch_laptop`). Listening lokal memerlukan file/cache utuh, screenshot teruji, dan playback audio resmi tugas yang dipilih; sukses suara sintetis hanya menguji kontrol. Untuk pindah, remote terkini harus terverifikasi, checkpoint/hasil tersinkron, serta tidak ada perubahan lokal yang tertinggal. Browser hasil boleh belum tersedia bila jalur screenshot yang relevan telah diuji; jelaskan jalur yang benar-benar dapat dipakai. Playback Listening dan rekaman Speaking memerlukan pemeriksaan langsung pada perangkat ini.

Rehearsal memakai **tes sistem**, bukan attempt belajar atau soal baru untuk diagnostik. Pengguna menekan Play sendiri pada contoh audio, mengirim screenshot contoh dan rekaman singkat. Coach menyimpan checkpoint, membaca ulang, lalu menguji resume pada chat baru dengan “lanjut”. Jangan menyebut rehearsal pengguna, audio atau rekaman berhasil jika belum dilakukan; tandai `not_tested` sampai ada bukti. Hasilnya dikecualikan dari progres Tata.

Setelah pemeriksaan berhasil, Tata cukup mengatakan **“Mulai”**. Laptop Tata belum diuji sampai pemeriksaan pada perangkat itu benar-benar dilakukan.

## 5. Backup otomatis yang diizinkan

Pengguna telah meminta autosync pada milestone dan heartbeat backup **setiap 1 jam**. Coach otomatis mencoba push sesudah checkpoint/hasil/feedback tersimpan serta dibaca ulang dan sesudah materi/pembaruan sistem diverifikasi; tidak perlu meminta persetujuan baru pada setiap push ke repo privat yang sama setelah autentikasi tersedia. Backup/publikasi dapat dilanjutkan meskipun screenshot/rekaman rehearsal masih menunggu. Tetap catat fitur itu sebagai belum diuji; backup berhasil tidak membuktikan kesiapan belajar.

Heartbeat dikelola dalam Codex pada laptop aktif ketika aplikasi tersedia, menggunakan runner berikut. Contoh ini untuk coach; Tata tidak perlu menjalankannya:

```sh
python3 scripts/hourly_sync.py --message "Backup IELTS Coach Tata"
```

Untuk folder lain gunakan `--root PATH`. Runner memeriksa sesi, feedback serta referensi koreksi, lalu memakai sinkronisasi Git yang aman. Writer lokal yang sibuk dapat menunda run; retry berikutnya mempertahankan ID/hasil. Git lock menserialkan backup milestone dan hourly. Status run ada pada `.local/scheduled-sync.json`; cache lokal ini tidak ikut clone/Git dan tidak menggantikan pemeriksaan remote aktual. Run rutin sukses/tanpa perubahan atau writer sibuk tetap diam; kegagalan atau kebutuhan tindakan yang baru/berubah diberi tahu tanpa notifikasi berulang untuk keadaan sama.

Clone baru tidak otomatis membuktikan credential, kesiapan, atau eksekusi jadwal pada laptop itu. Sebelum pindah, pastikan laptop asal telah tersinkron; hanya satu perangkat belajar aktif. Laptop tidur, Codex tidak tersedia, jaringan offline atau credential gagal dapat menunda backup. Bila ganti laptop, periksa tujuan folder heartbeat pada perangkat aktif; jangan menyalakan dua salinan sebagai perangkat belajar bersamaan. Jangan menyalin credential atau menambah automasi lain sebagai jalan pintas.

## Jika koneksi terputus

Pada komputer asal, push paket binary sempat menemui HTTP400. Pengiriman berhasil setelah pengaturan **repo lokal saja** berikut; gunakan sebagai pemeriksaan bila error yang sama terjadi pada jaringan laptop baru, bukan mengubah Git global:

```sh
git config --local http.version HTTP/1.1
git config --local http.postBuffer 52428800
```

Pengaturan ini memakai buffer maksimal 50 MiB untuk menghindari pengiriman chunked pada jalur yang bermasalah; verifikasi TLS tetap aktif. Setelah retry, pastikan status remote benar-benar synced sebelum pindah perangkat.

Coach menyimpan checkpoint/hasil pada laptop yang sama, membaca ulang, dan menandai **belum tersinkron**. Hasil tersimpan tetap sah sebagai catatan lokal meski push gagal; retry hanya menjalankan sinkronisasi, bukan menilai ulang. Lanjutkan attempt dengan **“Lanjut”** pada perangkat itu. Latihan lokal dapat dilanjutkan saat offline bila semua bahan yang diperlukan lengkap; cache koreksi yang tidak cocok/tidak lengkap membuat review menunggu. Saat koneksi kembali, coach menyinkronkan dan memastikan push berhasil sebelum Tata pindah laptop. Jika akses GitHub ditolak, jelaskan kendala autentikasi atau izin yang benar-benar terlihat; jangan menganggap akun Codex memberi akses GitHub otomatis.

Jangan mengedit folder mirror `.codex/.chatgpt-projects/`, sumber sinkron lain, pengaturan akun atau permissions. Izin automasi berlaku pada heartbeat backup per jam yang diminta; jangan memasang layanan, membuat automasi lain atau mengirim pesan sebagai bagian setup ini.

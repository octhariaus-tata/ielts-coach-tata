# IELTS Coach — Tata

Belajar IELTS Academic lewat chat Codex, dengan catatan dan bukti di folder project. GitHub privat menyimpan versi bersama agar belajar dapat dilanjutkan dari laptop lain setelah sinkronisasi berhasil.

Target kerja overall 6.5; minimum tiap skill 6.0 masih sementara. Tes direncanakan sekitar Januari 2027. Skor lama adalah laporan pengguna, dan trial 12 Oktober 2026 belum menjadi baseline kemampuan terkini.

## Untuk Tata

Suk menyiapkan folder sekali pada setiap laptop mengikuti [SETUP.md](SETUP.md). Setelah siap, buka chat di project **IELTS-Coach-Tata** dan gunakan:

| Katakan | Coach mengurus |
| --- | --- |
| **Mulai** | Mengambil versi terbaru, membaca progres, memberi tepat satu tugas; default 20 menit |
| **Done** | Membaca hasil yang tersedia, memberi feedback, menyimpan dan menyinkronkan catatan |
| **Lanjut** | Menyambung attempt yang terputus dengan ID yang sama |
| **Progres** | Merangkum bukti keempat skill dan satu tugas berikutnya |
| **Kesiapan** | Memeriksa apakah laptop ini siap digunakan |

Tata menekan **Play** sendiri pada latihan Listening. Jika coach tidak dapat membaca hasil pada browser saat itu, kirim screenshot yang memperlihatkan nomor soal dan jawaban atau review. Tidak perlu mengetik ulang seluruh jawaban.

Coach menyebut dua status secara terpisah: **tersimpan lokal** dan **tersinkron ke GitHub**. Saat belum tersinkron, lanjutkan di laptop yang sama dan tunggu sinkronisasi berhasil sebelum pindah. Gunakan satu laptop belajar aktif pada satu waktu.

## Laptop lain

Repo: [octhariaus-tata/ielts-coach-tata](https://github.com/octhariaus-tata/ielts-coach-tata), privat, branch `main`. Paket sudah terbit dan sinkronisasi dua arah diuji pada komputer asal. Kesiapan tiap perangkat serta status terbaru dicatat pada [STATUS.md](STATUS.md).

Login Codex dengan akun yang digunakan belajar, lalu Suk menyiapkan credential GitHub dan salinan folder terbaru. Login Codex dan login GitHub adalah dua hal terpisah. Sinkronisasi percakapan tidak memindahkan seluruh folder lokal. [Dokumentasi project OpenAI](https://learn.chatgpt.com/docs/projects).

Saat membuka folder pada laptop baru, kirim:

> Ini project IELTS Coach Tata dari repo privat octhariaus-tata/ielts-coach-tata. Baca AGENTS.md, PROFILE.md, PLAN.md, STATUS.md dan PROGRESS.md. Periksa kesiapan laptop ini dan status sinkronisasi sebelum memulai latihan. Saya akan mengatakan “mulai” saat siap belajar.

## Catatan yang disimpan

| File/folder | Kegunaan |
| --- | --- |
| `AGENTS.md` | Aturan coach, bukti dan sinkronisasi |
| `PROFILE.md`, `PLAN.md` | Profil, target dan rencana belajar adaptif |
| `TASK_BANK.md`, `materials.json` | Materi utama/cadangan serta status pemeriksaannya |
| `STATUS.md` | Kesiapan sistem, sesi aktif dan tugas berikutnya |
| `sessions/` | Catatan attempt dengan ID unik |
| `PROGRESS.md` | Riwayat lama dan ringkasan bukti sesi baru |
| `evidence/` | Screenshot atau bukti yang benar-benar tersedia |
| `AUDIT.md` | Temuan audit awal dan batas verifikasinya |
| `scripts/` | Alat lokal pencatatan dan sinkronisasi yang dipakai coach |

Sistem ini tidak menjadwalkan automasi. Perintah chat ditangani coach ketika chat dibuka. Diagnostik baru keempat skill dilakukan bertahap setelah pilot akses dan penyimpanan berhasil.

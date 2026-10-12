# IELTS Coach — Tata

Belajar IELTS Academic lewat chat Codex, dengan catatan dan bukti di folder project. GitHub privat menyimpan versi bersama agar belajar dapat dilanjutkan dari laptop lain setelah sinkronisasi berhasil.

Target kerja overall 6.5; minimum tiap skill 6.0 masih sementara. Tes direncanakan sekitar Januari 2027. Skor lama adalah laporan pengguna, dan trial 12 Oktober 2026 belum menjadi baseline kemampuan terkini.

## Untuk Tata

Suk menyiapkan folder sekali pada setiap laptop mengikuti [SETUP.md](SETUP.md). Setelah siap, buka chat di project **IELTS-Coach-Tata** dan gunakan:

| Katakan | Coach mengurus |
| --- | --- |
| **Mulai** | Memeriksa versi terbaru dan attempt aktif, membaca progres, memberi tepat satu tugas; default 20 menit |
| **Done** | Menyimpan respons dahulu, memeriksa bukti, memberi feedback yang didukung bukti, lalu menyinkronkan |
| **Lanjut** | Membuka respons tersimpan dan menyambung attempt yang terputus dengan ID yang sama |
| **Progres** | Merangkum bukti keempat skill dan satu tugas berikutnya |
| **Kesiapan** | Memeriksa apakah laptop ini siap digunakan |

Tata menekan **Play** sendiri pada latihan Listening. Jika coach tidak dapat membaca hasil pada browser saat itu, kirim screenshot yang memperlihatkan nomor soal dan jawaban atau review. Tidak perlu mengetik ulang seluruh jawaban. Respons awal tersimpan sebelum penilaian; revisi sesudah feedback disimpan terpisah. Bukti yang belum cukup membuat sesi menunggu bukti atau review, dengan ID yang sama.

Coach menyebut dua status secara terpisah: **tersimpan lokal** dan **tersinkron ke GitHub**. Gagal push tidak menghilangkan respons atau hasil; retry hanya menyinkronkan. Saat belum tersinkron, lanjutkan di laptop yang sama dan tunggu sinkronisasi berhasil sebelum pindah. Gunakan satu laptop belajar aktif pada satu waktu.

Sesuai permintaan pengguna, backup dicoba otomatis setelah checkpoint, hasil, feedback, serta materi/pembaruan sistem yang telah diverifikasi. Ada heartbeat Codex tambahan **setiap 1 jam pada laptop aktif ketika Codex tersedia**. Tata tidak perlu menjalankan Git atau menyetujui setiap push ulang. Run rutin sukses/tanpa perubahan tetap diam; kendala yang membutuhkan tindakan dilaporkan. Jadwal tidak menjamin backup saat laptop tidur, aplikasi tidak tersedia, offline atau credential gagal.

Empat sesi pendek berotasi **Listening → Reading → Speaking → Writing**. Writing singkat dan Speaking satu bagian mendapat feedback terbatas; estimasi band memerlukan sampel yang memadai. Saat offline, coach dapat melanjutkan latihan lokal jika semua bahan yang diperlukan tersedia, sambil menyebut batas verifikasi versi bersama.

Tata boleh memberi masukan biasa di chat: waktu terlalu sempit, feedback terlalu panjang, kendala akses, atau koreksi yang diragukan. Coach menyimpan teks serta asalnya, lalu memakai preferensi eksplisit Tata dan bukti baru untuk menyesuaikan tugas. Masukan pemilik tentang desain tetap dipisahkan dari preferensi Tata. Sistem belajar dari catatan; model tidak dilatih ulang dan skor tidak diganti otomatis. [Cara adaptasi](ADAPTATION.md).

Alur rutin memakai **1 coach utama + reviewer Astra sesuai kebutuhan**, dengan **2 skill khusus project: `ielts-coach` dan `ielts-github-sync`**. Skill kedua menangani backup yang telah diizinkan, bukan latihan otomatis. Pembagian agent saat membangun sistem, data, dan batas kesiapan dijelaskan dalam [SYSTEM.md](SYSTEM.md). Kesiapan teknis tidak berarti baseline keempat skill sudah tersedia.

## Laptop lain

Repo: [octhariaus-tata/ielts-coach-tata](https://github.com/octhariaus-tata/ielts-coach-tata), privat, branch `main`. Sinkronisasi paket v1 diuji melalui dua salinan pada komputer asal. Status pembaruan dan batas verifikasinya ada pada [STATUS.md](STATUS.md). Kesiapan perangkat disimpan lokal pada `.local/readiness.json`; salinan baru tetap memerlukan pemeriksaan sendiri.

Login Codex dengan akun yang digunakan belajar, lalu Suk menyiapkan credential GitHub dan salinan folder terbaru. Login Codex dan login GitHub adalah dua hal terpisah. Sinkronisasi percakapan tidak memindahkan seluruh folder lokal. [Dokumentasi project OpenAI](https://learn.chatgpt.com/docs/projects).

Saat membuka folder pada laptop baru, kirim:

> Ini project IELTS Coach Tata dari repo privat octhariaus-tata/ielts-coach-tata. Baca AGENTS.md, PROFILE.md, PLAN.md, STATUS.md dan PROGRESS.md. Periksa kesiapan laptop ini dan status sinkronisasi sebelum memulai latihan. Saya akan mengatakan “mulai” saat siap belajar.

## Catatan yang disimpan

| File/folder | Kegunaan |
| --- | --- |
| `AGENTS.md` | Aturan coach, bukti dan sinkronisasi |
| `SYSTEM.md`, `ADAPTATION.md` | Desain keseluruhan serta aturan adaptasi yang dapat diperiksa |
| `.agents/skills/ielts-coach/` | Skill project yang merujuk workflow dan CLI |
| `.agents/skills/ielts-github-sync/` | Skill backup milestone dan hourly untuk repo privat yang diizinkan |
| `PROFILE.md`, `PLAN.md` | Profil, target dan rencana belajar adaptif |
| `TASK_BANK.md`, `materials.json` | Materi utama/cadangan serta status pemeriksaannya |
| `STATUS.md` | Status sistem, sesi aktif dan tugas berikutnya |
| `sessions/` | Attempt dengan ID unik, checkpoint respons dan hasil review |
| `PROGRESS.md` | Riwayat lama dan ringkasan bukti sesi baru |
| `evidence/` | Screenshot atau bukti yang benar-benar tersedia |
| `feedback/`, `learning/` | Masukan mentah, analisis turunan dan ledger keputusan |
| `coach_refs/` | Cache key/transcript untuk koreksi coach; tidak dibagikan sebelum done |
| `.local/readiness.json` | Pemeriksaan fitur pada laptop ini; tidak ikut Git |
| `.local/scheduled-sync.json` | Status run backup pada laptop ini; tidak ikut Git |
| `AUDIT.md` | Temuan audit awal dan batas verifikasinya |
| `scripts/` | Alat lokal pencatatan dan sinkronisasi yang dipakai coach |

Coach memakai `scripts/coach.py` untuk menyiapkan sesi, checkpoint, menyelesaikan review, membaca status, dan mencatat feedback. Antrean diperbarui dari bukti setiap sesi ketika chat dibuka. Heartbeat hanya memeriksa dan menyinkronkan data yang sudah ada. Diagnostik baru keempat skill dilakukan bertahap setelah pilot akses dan penyimpanan berhasil. Screenshot serta rekaman rehearsal yang masih menunggu tidak menghalangi backup yang telah diizinkan dan tidak boleh dilabeli lulus. Versi baru disebut terbit hanya setelah push serta remote diperiksa; data rehearsal dan tes sistem tidak dihitung sebagai kemajuan Tata.

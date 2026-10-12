# Audit sistem IELTS Tata

Tanggal: 12 Oktober 2026. Audit berdasarkan brief pengguna, file lokal yang benar-benar dibaca, riwayat dua chat Codex terkait, UI project ChatGPT, serta sumber resmi yang dibuka. Rekomendasi dipisahkan dari bukti yang ditemukan.

## Fakta yang dapat dikonfirmasi

- Pengguna mengonfirmasi skor lama L 5.0, R 5.5, W 6.0, S 5.5 milik Tata; target overall 6.5, tes sekitar Januari 2027, tujuan LPDP S2. Dokumen hasil tes belum diperiksa.
- Pengguna memilih empat sesi 20 menit dan satu sesi panjang per minggu, lalu memilih Codex serta meminta folder awal untuk dipindahkan ke laptop Tata.
- [Project “IELTS - Tata”](https://chatgpt.com/g/g-p-6acb0a67d60c8191b353012bcfa558c8-ielts-tata/project) berhasil dibuka melalui browser setelah gangguan pemuatan sementara. Settings memperlihatkan Instructions kosong. Sources memperlihatkan keadaan kosong. Daftar chat project yang terlihat memuat **“IELTS Weekly Review”**; chat itu berhasil dibaca.
- Settings menyebut project bersama memakai Project-only memory dan Library access Disabled. Ini bukan bukti akses ke semua file di akun.
- Pada akun browser yang sedang membuka project, UI menampilkan **“Work requires upgrade”**. Jangan menganggap kemampuan akun browser sama dengan akun Codex pengguna saat ini atau akun di laptop Tata.
- Mirror lokal yang terbaca ada di `/Users/suk/.codex/.chatgpt-projects/g-p-6acb0a67d60c8191b353012bcfa558c8/`. File yang ditemukan: `AGENTS.md` dan `IELTS_LISTENING_SYSTEM.md`. `AGENTS.md` saat audit menyebut tidak ada custom instructions dan memperingatkan file mirror dapat diganti saat task baru dibuat.

## Rekonsiliasi riwayat akses dan skor

Brief menyebut hasil browser tidak dapat diakses, sedangkan log mengatakan skor 1/3 dibaca langsung. Riwayat lebih lengkap mengubah kesimpulan: pada sesi awal akses gagal; pada trial berikutnya, chat **“Check IELTS results visibility”** merekam panggilan untuk membaca tab, kemudian melaporkan tiga pilihan dan skor 1/3. Dua kejadian ini dapat sama-sama benar pada waktu berbeda.

Pengguna menyebut trial tersebut untuk mengecek apakah sistem bekerja. Maka skor 1/3 punya provenance historis, tetapi belum menjadi baseline kemampuan yang layak. Key/transcript resmi dibuka ulang dan konsisten dengan pembahasan terdahulu. Tidak ada screenshot hasil asli yang tersedia di folder baru; audit tidak mengklaim membaca ulang jawaban dari attempt asli. [Key](https://ielts.org/cdn/computer-delivered-sample-tests-listening/ielts-listening-computer-delivered-multiple-choice-one-answer-answer-key.pdf), [transcript](https://ielts.org/cdn/computer-delivered-sample-tests-listening/ielts-listening-computer-delivered-multiple-choice-one-answer-transcript.pdf).

Riwayat juga menyebut pengeditan `AGENTS.md` mirror, tetapi file sekarang kembali tanpa custom instructions dan project asli memang kosong. Penjelasan bahwa mirror dibuat ulang sesuai instruksi file adalah kemungkinan, bukan penyebab yang telah dibuktikan. Mengedit mirror tidak boleh dianggap sama dengan menyimpan Project Instructions di layanan ChatGPT.

## Target dan syarat

Listening 6.5 saja tidak memenuhi target overall dengan skor lain tetap: (6.5 + 5.5 + 6.0 + 5.5) / 4 = 5.875, dibulatkan menjadi overall 6.0. Contoh target kerja L/R 6.5 dan W/S 6.0 menghasilkan rata-rata 6.25, overall 6.5. [Aturan scoring resmi](https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail).

Pada LPDP SHARE Tahap 2 2026, kriteria umum pendanaan penuh menyebut IELTS 6.5 untuk magister luar negeri dan 6.0 untuk dalam negeri. Bagian itu tidak menetapkan minimum 6.0 setiap komponen. Jalur/kriteria lain dapat berbeda; ketentuan kampus Tata belum diketahui, dan panduan ini tidak mengonfirmasi aturan periode 2027. Target setiap skill 6.0 tetap sementara. [LPDP SHARE 2026](https://lpdp.kemenkeu.go.id/beasiswa/beasiswa-share/beasiswa-share/).

Tiga soal tidak dapat dikonversi secara andal menjadi band Listening. Penilaian Listening lengkap menggunakan 40 soal dan ambang dapat sedikit berbeda antarversi. [Scoring IELTS](https://ielts.org/take-a-test/your-results/ielts-scoring-in-detail).

Kenaikan overall 5.5 ke 6.5 dalam 12 minggu belum dapat dipastikan realistis tanpa baseline baru dan waktu aktual. Rekomendasi: mulai dengan kapasitas yang dipilih, ukur ulang pada minggu 2/4, lalu ubah porsi latihan atau waktu bila bukti menunjukkan kebutuhan.

## Perbandingan alur praktis

| Alur | Usaha Tata | Keandalan dan penggunaan |
| --- | --- | --- |
| Latihan resmi + jawaban dibaca browser | Kerjakan, lalu “done” | Pilihan utama jika akses halaman hasil saat ini sudah terbukti. Tetap cocokkan dengan key; jangan bergantung pada auto-score yang belum diperiksa |
| Latihan resmi + screenshot review/jawaban | Kerjakan, lalu kirim screenshot yang cukup | Fallback stabil. Mendukung koreksi per soal bila jawaban dan versi materi jelas; skor total saja belum mendukung diagnosis kesalahan |
| Voice + latihan buatan AI | Interaksi singkat melalui suara | Cocok untuk drill tambahan; tandai IELTS-style buatan AI, pisahkan dari skor latihan resmi dan checkpoint kesiapan |

Halaman IELTS.org benar-benar menyediakan sample Judy dan furnitur, beserta key/transcript. Label furnitur sebagai British Council dalam chat lama tidak didukung link langsung tugas yang sama; coach harus menyebut provider dan URL yang benar. Ketersediaan daftar sumber tidak membuktikan player, audio, atau auto-scoring berfungsi pada setiap sesi. [Sample resmi IELTS](https://ielts.org/take-a-test/preparation-resources/sample-test-questions/academic-test).

## Rekomendasi implementasi

Gunakan folder lokal ini sebagai sumber utama dengan `AGENTS.md`, profil, plan, log, dan evidence. Tata cukup menggunakan satu chat belajar pada project Codex tersebut; pemilihan tugas dan pengelolaan file menjadi pekerjaan coach. Ambil baseline baru untuk empat skill, dengan Listening mendapat porsi awal lebih besar.

Folder lokal bisa dilampirkan ke local project, sementara project ChatGPT memakai sumber dan instruksinya sendiri. Login/sinkronisasi chat tidak otomatis memindahkan folder antar laptop. [Dokumentasi project OpenAI](https://learn.chatgpt.com/docs/projects?surface=app).

Belum dilakukan: pendaftaran folder di sidebar, perubahan project cloud, upload file, pengaturan akun, automasi, atau latihan baru. Folder dan ZIP hanya paket awal. Tata masih perlu memindahkan folder dan membukanya pada local project di laptop yang dipakai belajar.

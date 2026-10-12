# Kartu harian IELTS Tata — workflow sederhana

Permintaan pemilik: kartu tugas sudah disiapkan sekitar pukul 09.00 WIB pada **weekdays saja**. Persiapan dijadwalkan mulai 08.45 WIB Senin–Jumat. Waktu ini untuk persiapan, bukan kewajiban Tata belajar tepat pukul 09.00. Laptop dan aplikasi perlu berjalan agar pekerjaan lokal dapat dieksekusi.

Tata membuka chat belajar, mengatakan **mulai**, menjawab, lalu **done**. Coach menangani kesiapan fitur yang relevan, pilihan satu tugas, checkpoint, review dan sinkronisasi melalui alat yang sudah ada. **Lanjut** tetap tersedia untuk sesi terputus. Tidak perlu perintah kesiapan terpisah setiap hari. Pemeriksaan fitur dilakukan saat fitur akan dipakai; screenshot/rekaman yang belum diuji tetap dilabeli belum diuji. Jadwal tidak mengubah batas penilaian atau melewati syarat publikasi yang masih berlaku.

| Hari | Kegiatan awal | Waktu Tata |
| --- | --- | --- |
| Senin | Listening; awalnya Packham form Q1–8 | 20 menit |
| Selasa | Reading; awalnya Marie Curie True/False/Not Given | 20 menit |
| Rabu | Speaking; awalnya Part 2, An Important Possession | 20 menit |
| Kamis | Writing; awalnya Tourism Task 2: posisi, outline dan satu paragraf | 20 menit |
| Jumat | Recap hasil yang tersedia dari minggu itu; satu perbaikan per skill dan satu prioritas | 20 menit |
| Sabtu–Minggu | Tidak ada scheduled task atau tugas wajib | Istirahat |

Senin–Kamis masing-masing satu topik fokus: attempt, pembahasan, lalu satu perbaikan pada topik itu. Jadwal mulai 13 Oktober 2026 dengan **Reading**, sesuai koreksi pengguna bahwa hari ini sudah Listening. Listening 12 Oktober adalah laporan pengguna; detail attempt, jawaban dan skor belum tersedia dan tidak dibuat-buat. Jumat pertama hanya merekap skill dengan bukti nyata yang tersedia. Sesi panjang belum ditetapkan. Jika ada sesi aktif pada hari latihan, kartu mengarahkan lanjut dengan ID yang sama. Jika hari belajar terlewat tanpa attempt, tidak ada utang; slot berikutnya tetap berjalan. Jumat mencantumkan sesi belum selesai tanpa menutup atau menilainya. Review bukan tes baru, dan Writing pendek tidak mendapat band utuh.

## Pekerjaan terjadwal

Gunakan satu scheduled task di chat ini. Setiap run membaca catatan terbaru dan menjalankan:

```sh
python3 scripts/daily_card.py --save
```

Script memeriksa prompt/audio/cache lokal, menghitung antrean dari data yang tersimpan, dan membuat satu kartu bertanggal pada `.local/proactive/`. Script tidak membuat sesi, mengubah skor/profil/plan, menjalankan audio, submit attempt, commit/push atau mengubah file yang sedang dikerjakan chat utama. Sistem tes dikecualikan. Kartu hanyalah persiapan dari snapshot lokal; ketika mulai, coach memeriksa data dan sinkronisasi kembali. Jika run terlewat karena laptop mati, coach dapat membuat kartu saat Tata membuka chat.

Ketika **mulai**, baca kartu bertanggal hari ini atau bangun ulang. Untuk `study`, berikan `task_id` pada `coach.py prepare --task ID`; kalender tidak bergantung pada default antrean yang mungkin masih menunjuk Listening karena laporan hari ini belum mempunyai record hasil. Untuk `resume`, gunakan ID aktif tanpa mengulang audio. Untuk `weekly_recap`, baca hasil minggu itu dan beri satu latihan perbaikan berlabel review; jangan membuka attempt baru dengan soal lama atau menilai ulang skor. Jawaban recap dapat disimpan sebagai checkpoint `purpose: review` pada sesi terkait, tanpa mengubah hasil awal. Jika bukti belum tersedia, laporkan keterbatasan dan satu tindakan berikutnya.

Output ke Tata singkat: **hari/tanggal · skill/topik · durasi · fokus · satu tindakan**. Berikan satu tugas; cadangan disimpan untuk coach dan tidak menjadi menu pilihan. Soal/audio disampaikan setelah mulai agar sesi dibuat sebelum attempt. Key dan transcript tidak ditampilkan sebelum done.

Saat bank mendekati habis atau cache gagal, coach menerima satu tindakan pemeliharaan: siapkan kandidat resmi baru dengan sumber dan status verifikasi. Simpan draf kandidat pada `.local/proactive/` hingga dapat dimasukkan dan diperiksa oleh workflow materi project; jangan mengaku kandidat siap hanya dari link. Jangan mengulang tugas yang telah terekspos key sebagai pengukuran baru.

Jumat, gunakan hasil learner minggu itu dan analisis adaptasi untuk recap: bukti yang tersedia, satu perbaikan per skill yang sudah dicoba, satu fokus berikutnya, serta kendala nyata. Jika tidak ada hasil baru, tidak ada klaim peningkatan atau baseline. Preferensi pemilik tentang jadwal kartu bukan preferensi kemampuan atau waktu belajar Tata. Tidak ada rewriting otomatis skill, target, grading policy atau kode dari feedback.

## Praktik Codex yang dipakai

Instruksi stabil dan skill mengatur cara bekerja; scheduled task menjalankan rutinitas yang sudah diuji. Tata memakai satu coach; pekerjaan terjadwal mengurus persiapan dan review. [Panduan praktik Codex](https://learn.chatgpt.com/guides/best-practices), [scheduled tasks](https://learn.chatgpt.com/docs/automations).

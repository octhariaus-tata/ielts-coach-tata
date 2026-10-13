# Status IELTS Coach Tata

Diperbarui: 12 Oktober 2026, Asia/Jakarta. v1.1, adaptasi v1.2 dan autosync selesai di file lokal. Pengguna mengizinkan backup milestone serta tiap satu jam; sinkronisasi pertama berhasil pada commit b755d41eb7e303e201cb4c4d0dd0bf42eda52a16; 75 file pada salinan kedua cocok byte dengan milestone tersebut. Screenshot dan rekaman rehearsal tetap menunggu, tanpa menghalangi backup.

| Komponen | Status saat ini |
| --- | --- |
| Repo bersama | v1.2 beserta skill/jadwal autosync terbit di repo privat `octhariaus-tata/ielts-coach-tata`, branch `main`; status Git aktual diperiksa setiap run |
| Sinkronisasi | Milestone v1.2/autosync berhasil dipush dan diambil salinan kedua; 75 file commit b755d41 cocok SHA256. Dua clone pada laptop ini. Status aktual diperiksa setiap run |
| Sistem pencatatan | v1.1: checkpoint sebelum penilaian, respons/revisi terpisah, fase menunggu, retry tanpa menilai ulang. Riwayat lama dipertahankan; belum ada latihan baru Tata |
| Bank tugas | 8 tugas resmi; 8 PDF soal tanpa key + MP3 Packham 154,57 detik dan Social Contact 92,59 detik tersedia lokal. Playback oleh Tata belum diperiksa |
| Pengujian sinkronisasi | 18 tes integrasi lulus, termasuk whitelist feedback/ledger/skill. Round-trip GitHub produksi v1 sebelumnya terverifikasi; milestone baru sudah dipush dan verified remote, commit b755d41. Dua salinan berada pada satu komputer, bukan dua laptop |
| Sesi dan ID aktif | Lihat bagian Keadaan sesi di bawah; dikelola dari sessions/ |
| Baseline kemampuan terkini | Belum tersedia; trial tiga soal adalah tes sistem |
| Laptop Tata | Belum tersedia untuk pemeriksaan; akses file/browser/hasil belum diuji |
| Speaking dengan rekaman | Menunggu rekaman pendek pengguna; belum terverifikasi |
| Rehearsal v1.1 | Tiga beep sintetis terdengar menurut pengguna; chat baru memulihkan ID 2026-10-12-listening-1729392fd5b8 dan satu checkpoint. Screenshot/rekaman masih menunggu; tes sistem tidak dihitung sebagai progres |
| Adaptasi v1.2 | Feedback mentah + sumber, preferensi eksplisit per scope, hipotesis berulang dari soal baru, karantina sengketa, dan ledger eksperimen. Baseline masih insufficient; belum ada klaim peningkatan band |
| Pengujian sistem | 148 tes berbeda lulus; Astra menguji perilaku skill pada fixture terisolasi dan menutup temuan sumber bukti/bantuan. Tes bukan bukti naik band atau kesiapan seluruh fitur pengguna |
| Skill project | 2 skill portable: ielts-coach dan ielts-github-sync; 6 modul Python |
| Jadwal backup | ACTIVE: IELTS GitHub sync tiap jam, satu jam sekali di chat lokal ini. Memerlukan laptop dan Codex berjalan serta akses GitHub. Deferral bila writer/Git sibuk; satu percobaan per run |
| Referensi offline | Empat cache key/transcript/teks resmi dalam coach_refs/ lolos versi, nomor, provenance dan checksum; hanya untuk coach sesudah done |
| Kesiapan perangkat | File/correction cache lulus; kontrol playback sintetis terverifikasi. Audio IELTS resmi belum diputar; screenshot dan rekaman belum diuji. Status mutakhir: coach.py status |

## Tugas berikutnya

Preferensi global Tata, 13 Oktober 2026: siapkan cukup soal/materi untuk sesi belajar yang berbobot pada setiap run, beserta review kesalahan dan penerapan perbaikan. Sumber mentah: `feedback/2026-10-13-learner-study-volume-global.json`. Jumlah menyesuaikan skill dan budget waktu; tidak ada durasi baru atau jumlah minimum universal yang dinyatakan. Untuk hari ini, alur yang disetujui adalah Packham 8 soal → review → Social Contact 6 soal → review akhir (14 soal baru total; estimasi coach 25–30 menit). Siapkan tugas berikutnya setelah attempt pertama selesai dan periksa materi saat itu; simpan tiap attempt dengan ID terpisah. Preferensi ini bukan bukti kemampuan atau perubahan target IELTS.

Saat belum ada sesi belajar selesai: Listening Packham, soal 1–8, maksimum 20 menit termasuk feedback. Berikan `materials/listening-packham-form.pdf` dan audio lokal; Tata menekan Play sendiri, lalu mengirim jawaban awal langsung di chat atau foto/screenshot lembar jawabannya, diakhiri done. Cadangan siap lokal: Making Social Contact in the UK, soal 11–16, `materials/listening-social-contact-short-answer.pdf` beserta audio. Library guide hanya referensi online opsional. Setelah sesi selesai, ikuti tugas berikutnya pada bagian Keadaan sesi. Judy dan furnitur hanya untuk review.

## Pengarahan belajar terbaru — 13 Oktober 2026

Preferensi berkelanjutan eksplisit Tata: menulis dalam bahasa Inggris saat belajar; coach memakai bahasa Inggris yang jelas untuk mendukungnya. Urutan setiap pelajaran: materi/penjelasan → worked example beserta alasan → latihan bersama → latihan mandiri. Sumber mentah: feedback/2026-10-13-learner-english-teaching-sequence.json. Tidak ada perubahan durasi atau target. Preferensi dicatat di sini karena schema sinyal terstruktur belum memiliki language/lesson-sequence.

Review lima latihan dan materi contoh tersedia di [English review](learning/coaching-notes/2026-10-13-english-review.md), berdasarkan feedback/2026-10-13-learner-teach-before-test.json. Revisi Tourism yang diminta pada hasil awal sudah diterima; belum pengukuran independen. Berikan penjelasan satu konsep dan worked example sebelum latihan, sambil menjaga alur cepat sesuai masukan Tata.

Tugas pedagogis berikut: mini-lesson verb forms/agreement; cadangan pedagogis: worked example TFNG (contoh coach buatan AI). Paket Listening resmi baru belum siap dan perlu preflight sebelum ditugaskan. Tidak ada attempt baru pada review ini. Skor lama dipertahankan; belum ada band IELTS terkini.

## Latihan tambahan terbaru — 13 Oktober 2026

Present-simple set 01 buatan coach: 11/12 setelah materi/contoh/guided practice, tanpa band atau klaim mastery. Bukti: evidence/practice/2026-10-13-present-simple-set01.json. Koreksi Q5 sudah diterima: The guide helps visitors, tersimpan sebagai review tanpa mengganti 11/12. Materi berikutnya siap di learning/coaching-notes/2026-10-13-present-simple-negatives-lesson.md: do not/does not → worked example → guided → independent. Satu set ini bukan baseline IELTS; paket Listening resmi baru masih perlu preflight.

Guided negatives diterima benar: Tourism doesn't help local businesses. Bukti evidence/guided/2026-10-13-present-simple-negatives-01.json. Set 12 kalimat negatif sudah direview: 12/12 untuk struktur grammar, typo cuastomers/Thet dicatat terpisah pada evidence/practice/2026-10-13-present-simple-negatives-set01.json. Materi berikutnya siap: learning/coaching-notes/2026-10-13-present-simple-questions-lesson.md; Do/Does questions → worked example → guided → independent. Drill buatan coach, bukan attempt IELTS.

Guided questions diterima: Does your sister work in a hospital ? — grammar benar; my → your adalah perubahan referen, tepat bila bertanya kepada coach tetapi tugas transformasi mempertahankan my. Bukti evidence/guided/2026-10-13-present-simple-questions-01.json. Set questions selesai direview: 12/12 grammar, kapitalisasi/tanda baca terpisah pada evidence/practice/2026-10-13-present-simple-questions-set01.json. Materi berikut: learning/coaching-notes/2026-10-13-present-simple-short-answers-lesson.md → worked example → guided → independent.

## Cara memperbarui

Coach memperbarui kesiapan setelah ada bukti. Status sesi berasal dari catatan `sessions/`; gunakan alat sesi untuk membuat, melanjutkan dan menutup attempt, lalu baca ulang record serta ringkasannya. “Done” berulang memakai ID semula. Simpan hasil lokal dahulu; ubah klaim sinkronisasi hanya setelah status Git dan push benar-benar diperiksa.

Jangan menandai laptop baru siap berdasarkan keberhasilan komputer ini. Bila offline atau versi berbeda, sebutkan batasnya dan lanjutkan hanya di perangkat yang memiliki catatan aktif sampai sinkronisasi selesai.

<!-- managed-sessions:start -->
## Keadaan sesi — dibaca dari sessions/

- Sesi belajar aktif: tidak ada.
- Sesi belajar selesai: 5.
- Tes sistem tidak dihitung sebagai kemajuan Tata.
- Tugas berikutnya: Satu revisi micro-task Tourism 3–4 kalimat untuk menerapkan feedback; sesudah review lanjut rotasi Listening dengan paket resmi baru yang perlu dipreflight, bukan retake bank yang key-nya telah terekspos.
<!-- managed-sessions:end -->

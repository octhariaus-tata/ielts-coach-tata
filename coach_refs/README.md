# Referensi koreksi lokal — hanya coach

Empat cache JSON berisi cuplikan **key resmi dan transcript/teks Reading** dari PDF IELTS Sample Tasks 2023 yang sama dengan prompt di `materials/`. Jangan memberikan folder, file cache, atau full source PDF kepada Tata sebelum attempt selesai. `scripts/references.py` mengembalikan metadata pemeriksaan tanpa jawaban; `learner_packet()` hanya mengembalikan prompt/audio dan informasi tugas yang aman.

| Tugas | Prompt sumber (halaman PDF) | Key | Transcript/teks bukti |
| --- | --- | --- | --- |
| Packham, soal 1–8 | 3 | 7 | transcript 4–6 |
| Social Contact, soal 11–16 | 11 | 13 | transcript 12 |
| Marie Curie, soal 1–3 | 12–13 | 14 | teks Reading 12–13 |
| Development of Rockets, soal 7–10 | 3–4 | 5 | teks Reading 3–4 |

Sumber resmi diambil ulang 12 Oktober 2026. SHA256 full PDF Listening dan Reading cocok dengan provenance ekstraksi prompt sebelumnya; full PDF hanya digunakan sementara untuk pemeriksaan dan tidak disimpan dalam repo. Setiap cache menyimpan URL sumber, SHA256 sumber, tanggal pemeriksaan, nomor halaman/soal, pemetaan checksum prompt, teks cuplikan sumber, serta key terstruktur yang dibandingkan dengan teks answer page asli. Checksum cache disimpan di `materials.json`.

Key mempertahankan alternatif bertanda slash, kata opsional dalam kurung, dan pasangan jawaban yang boleh bertukar urutan. Coach tetap memeriksa jawaban awal Tata dan memberi bukti sesudah **done**; alat tidak otomatis menetapkan kebenaran padanan baru. Kedua tugas Listening membatasi jawaban **NO MORE THAN THREE WORDS AND/OR A NUMBER**. Transcript PDF tidak menyediakan timestamp.

Pemeriksaan offline gagal bila file hilang/berubah, versi atau rentang salah, key tidak lengkap, atau provenance prompt tidak cocok. Status **passed** membuktikan ketersediaan/integritas cache, bukan playback, akses hasil browser, jawaban Tata, atau band IELTS. Jika gagal, pertahankan hasil lokal dan tunggu referensi versi yang sama; jangan mengarang koreksi.

Sumber: [Listening resmi](https://ielts.org/cdn/Sample-tests/ielts-listening-sample-tasks-2023.pdf), [Academic Reading resmi](https://ielts.org/cdn/Sample-tests/ielts-academic-reading-sample-tasks-2023.pdf).

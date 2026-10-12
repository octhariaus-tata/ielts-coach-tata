# Implementasi sistem — 12 Oktober 2026

## Hasil lokal

- Coach mempunyai perintah chat mulai/done/lanjut/progres/kesiapan; sesi disimpan atomik dan dibaca ulang. ID tetap untuk lanjut dan done berulang.
- Snapshot materi pada setiap sesi mempertahankan judul/provider/URL/versi; nomor soal, total, dan key harus sesuai snapshot. Skor parsial hanya menghitung jawaban yang terbaca; skor total tidak menghasilkan pola per soal.
- Ringkasan sesi ditambahkan dalam marker pada PROGRESS.md dan STATUS.md. Riwayat lama, skor yang dilaporkan, serta provenance trial tidak dihapus. Belum ada latihan/diagnostik baru Tata.
- 8 tugas resmi disiapkan; 7 PDF prompt-only dan MP3 Packham tersedia di materials/. Halaman sumber, checksum dan QA dicatat dalam materials/PROVENANCE.json. Audio 154,57 detik dikenali sebagai MP3; tidak diputar coach. Packham Q1–8 adalah tugas pertama.
- Library guide dibuka melalui browser; layar awal hanya menampilkan instruksi serta Play. Coach tidak menekan Play. Prompt di balik gate dan akses hasil belum terverifikasi. Bank menandainya sebagai cadangan bersyarat.

## Pengujian

29 tes berbeda lulus: 15 untuk sesi dan 14 untuk sinkronisasi. Bukti: evidence/system/2026-10-12-session-tests.txt (15 sesi terbaru), evidence/system/2026-10-12-tests.txt (run gabungan sebelumnya 12 sesi + 14 sync).

Tes mencakup dua clone dengan bare remote sementara, transfer PNG/PDF/MP3 byte-identik, versi tertinggal, offline, penolakan push tanpa kehilangan commit, konflik, tujuan remote salah, done berulang, record corrupt ditolak sebelum ditulis, key berbeda, nomor soal di luar materi, skor total/parsial, larangan band cuplikan, dan pronunciation tanpa audio. Semua data simulasi berada dalam folder sementara, bukan kemajuan Tata.

Screenshot sebagian diuji pada level input jawaban yang sudah dibaca; tes ini tidak membuktikan OCR atau akses hasil browser di laptop Tata. Coach tetap membatasi penilaian pada isi yang benar-benar dapat dibaca.

## GitHub dan perangkat

Pemilik repo berubah dari rancangan SukrajPutera menjadi octhariaus-tata atas pilihan eksplisit pengguna. Repo privat https://github.com/octhariaus-tata/ielts-coach-tata dibuat dengan branch main; bukti UI ada di evidence/system/2026-10-12-github-private.jpg. Publikasi paket via browser masih sedang diselesaikan saat catatan ini dibuat.

Git HTTPS lokal ke repo ditolak karena credential tidak valid; konektor GitHub akun SukrajPutera mengembalikan404 untuk repo ini. Tidak mengubah konektor, collaborator, credential, settings akun atau permissions untuk mengatasinya. GitHub web login tidak membuktikan login Git lokal. Alat sync tersedia dan diuji, tetapi akses remote produksi belum siap.

Laptop Tata belum tersedia. macOS diuji di komputer ini; Windows/Linux, playback audio oleh Tata, pembacaan hasil pada laptop belajar, serta Speaking dengan rekaman belum diuji. Setup pertama dan satu round-trip sinkronisasi diperlukan pada setiap laptop baru.

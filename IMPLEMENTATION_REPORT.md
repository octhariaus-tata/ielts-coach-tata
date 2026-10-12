# Implementasi sistem — 12 Oktober 2026

## Hasil lokal

- Coach mempunyai perintah chat mulai/done/lanjut/progres/kesiapan; sesi disimpan atomik dan dibaca ulang. ID tetap untuk lanjut dan done berulang.
- Snapshot materi pada setiap sesi mempertahankan judul/provider/URL/versi; nomor soal, total, dan key harus sesuai snapshot. Skor parsial hanya menghitung jawaban yang terbaca; skor total tidak menghasilkan pola per soal.
- Ringkasan sesi ditambahkan dalam marker pada PROGRESS.md dan STATUS.md. Riwayat lama, skor yang dilaporkan, serta provenance trial tidak dihapus. Belum ada latihan/diagnostik baru Tata.
- 8 tugas resmi disiapkan; 7 PDF prompt-only dan MP3 Packham tersedia di materials/. Halaman sumber, checksum dan QA dicatat dalam materials/PROVENANCE.json. Audio 154,57 detik dikenali sebagai MP3; tidak diputar coach. Packham Q1–8 adalah tugas pertama.
- Library guide dibuka melalui browser; layar awal hanya menampilkan instruksi serta Play. Coach tidak menekan Play. Prompt di balik gate dan akses hasil belum terverifikasi. Bank menandainya sebagai cadangan bersyarat.

## Pengujian

30 tes berbeda lulus: 16 untuk sesi dan 14 untuk sinkronisasi. Bukti run gabungan terbaru: evidence/system/2026-10-12-tests.txt. Run sesi sebelumnya disimpan untuk provenance dalam evidence/system/2026-10-12-session-tests.txt.

Tes mencakup dua clone dengan bare remote sementara, transfer PNG/PDF/MP3 byte-identik, versi tertinggal, offline, penolakan push tanpa kehilangan commit, konflik, tujuan remote salah, done berulang, record corrupt ditolak sebelum ditulis, key berbeda, nomor soal di luar materi, skor total/parsial, larangan band cuplikan, dan pronunciation tanpa audio. Semua data simulasi berada dalam folder sementara, bukan kemajuan Tata.

Screenshot sebagian diuji pada level input jawaban yang sudah dibaca; tes ini tidak membuktikan OCR atau akses hasil browser di laptop Tata. Coach tetap membatasi penilaian pada isi yang benar-benar dapat dibaca.

## GitHub dan perangkat

Pemilik repo berubah dari rancangan SukrajPutera menjadi octhariaus-tata atas pilihan eksplisit pengguna. Repo privat https://github.com/octhariaus-tata/ielts-coach-tata dibuat dengan branch main; bukti UI ada di evidence/system/2026-10-12-github-private.jpg. Dokumen utama diterbitkan via browser pada commit e3353fcc1e31a78fc531437c32b21d421d08e655; materi dan alat sedang diterbitkan via Git.

Awalnya Git HTTPS lokal ditolak karena credential tidak valid, dan konektor GitHub akun SukrajPutera mengembalikan404 untuk repo ini. Pengguna kemudian mengizinkan unduhan GitHub CLI resmi lokal dan menyelesaikan sendiri otorisasi akun octhariaus-tata. Kelanjutan login sempat ditolak review otomatis sebelum persetujuan scope diberikan; diteruskan sesudah pengguna mengonfirmasi otorisasi. API CLI memverifikasi repo private=true, default_branch=main, serta akses push. Tidak mengganti konektor atau menambahkan collaborator.

GitHub CLI v2.102.0 arm64 diunduh hanya ke .local/bin/gh; checksum SHA256 dari rilis resmi cocok (da922c20d1792e5b2cbf375593d7a658acf034c12c84e007e71c76ef959c337e). Konfigurasi CLI dan helper berada di .local/ yang diabaikan Git. Autentikasi Git memakai konfigurasi repo lokal; konfigurasi Git global tidak diubah. Credential tidak disalin ke repo atau laptop lain. Round-trip remote produksi sedang diverifikasi.

Laptop Tata belum tersedia. macOS diuji di komputer ini; Windows/Linux, playback audio oleh Tata, pembacaan hasil pada laptop belajar, serta Speaking dengan rekaman belum diuji. Setup pertama dan satu round-trip sinkronisasi diperlukan pada setiap laptop baru.

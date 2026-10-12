# Implementasi sistem — 12 Oktober 2026

## Hasil lokal

- Coach mempunyai perintah chat mulai/done/lanjut/progres/kesiapan; sesi disimpan atomik dan dibaca ulang. ID tetap untuk lanjut dan done berulang.
- Snapshot materi pada setiap sesi mempertahankan judul/provider/URL/versi; nomor soal, total, dan key harus sesuai snapshot. Skor parsial hanya menghitung jawaban yang terbaca; skor total tidak menghasilkan pola per soal.
- Ringkasan sesi ditambahkan dalam marker pada PROGRESS.md dan STATUS.md. Riwayat lama, skor yang dilaporkan, serta provenance trial tidak dihapus. Belum ada latihan/diagnostik baru Tata.
- 8 tugas resmi disiapkan; 8 PDF prompt-only dan 2 MP3 tersedia di materials/. Halaman sumber, checksum dan QA dicatat dalam materials/PROVENANCE.json. Audio Packham 154,57 detik dan Social Contact 92,59 detik dikenali sebagai MP3; tidak diputar coach. Packham Q1–8 adalah tugas pertama, Social Contact Q11–16 cadangan.
- Library guide dibuka melalui browser; layar awal hanya menampilkan instruksi serta Play. Coach tidak menekan Play. Prompt di balik gate dan akses hasil belum terverifikasi. Karena itu tidak dijadikan cadangan siap pakai; disimpan sebagai referensi online opsional.

## Pengujian

30 tes berbeda lulus: 16 untuk sesi dan 14 untuk sinkronisasi. Bukti run gabungan terbaru: evidence/system/2026-10-12-tests.txt. Run sesi sebelumnya disimpan untuk provenance dalam evidence/system/2026-10-12-session-tests.txt.

Tes mencakup dua clone dengan bare remote sementara, transfer PNG/PDF/MP3 byte-identik, versi tertinggal, offline, penolakan push tanpa kehilangan commit, konflik, tujuan remote salah, done berulang, record corrupt ditolak sebelum ditulis, key berbeda, nomor soal di luar materi, skor total/parsial, larangan band cuplikan, dan pronunciation tanpa audio. Semua data simulasi berada dalam folder sementara, bukan kemajuan Tata.

Screenshot sebagian diuji pada level input jawaban yang sudah dibaca; tes ini tidak membuktikan OCR atau akses hasil browser di laptop Tata. Coach tetap membatasi penilaian pada isi yang benar-benar dapat dibaca.

## GitHub dan perangkat

Pemilik repo berubah dari rancangan SukrajPutera menjadi octhariaus-tata atas pilihan eksplisit pengguna. Repo privat https://github.com/octhariaus-tata/ielts-coach-tata dibuat dengan branch main; bukti UI ada di evidence/system/2026-10-12-github-private.jpg. Dokumen utama diterbitkan via browser pada commit e3353fcc1e31a78fc531437c32b21d421d08e655; materi dan alat lengkap diterbitkan via Git.

Awalnya Git HTTPS lokal ditolak karena credential tidak valid, dan konektor GitHub akun SukrajPutera mengembalikan404 untuk repo ini. Pengguna kemudian mengizinkan unduhan GitHub CLI resmi lokal dan menyelesaikan sendiri otorisasi akun octhariaus-tata. Kelanjutan login sempat ditolak review otomatis sebelum persetujuan scope diberikan; diteruskan sesudah pengguna mengonfirmasi otorisasi. API CLI memverifikasi repo private=true, default_branch=main, serta akses push. Tidak mengganti konektor atau menambahkan collaborator.

GitHub CLI v2.102.0 arm64 diunduh hanya ke .local/bin/gh; checksum SHA256 dari rilis resmi cocok (da922c20d1792e5b2cbf375593d7a658acf034c12c84e007e71c76ef959c337e). Konfigurasi CLI dan helper berada di .local/ yang diabaikan Git. Autentikasi Git memakai konfigurasi repo lokal; konfigurasi Git global tidak diubah. Credential tidak disalin ke repo atau laptop lain.

Push awal dengan Git bawaan menemui HTTP400. Commit tetap lokal dan tidak dianggap sukses. Pengiriman ulang dengan HTTP/1.1 dan postBuffer 50 MiB berhasil menerbitkan commit 6f17628a2bf75f765da1d26ef07319fc0ad2d65d; konfigurasi workaround hanya di kedua repo lokal. TLS tetap diverifikasi.

Round-trip GitHub produksi berhasil: paket dengan backup offline pada commit 76680317f92cd8545c9784e1537321a228349413 diambil pada salinan kedua; 34 file tracked cocok SHA256. Marker tes sistem ditulis di salinan kedua, push menghasilkan commit 5aacfe7d8507c93ce22572452efbaa83fc095e13, lalu pull di folder utama membaca marker yang sama dan melaporkan synced/remote_verified=true, ahead=0, behind=0, pending_files kosong. Bukti: evidence/system/2026-10-12-github-roundtrip.txt. Kedua salinan ada pada komputer macOS ini, bukan bukti lintas laptop.

Laptop Tata belum tersedia. macOS diuji di komputer ini; Windows/Linux, playback audio oleh Tata, pembacaan hasil pada laptop belajar, serta Speaking dengan rekaman belum diuji. Setup pertama dan satu round-trip sinkronisasi diperlukan pada setiap laptop baru.


## Pembaruan v1.1 — implementasi lokal, publikasi menunggu rehearsal

Empat operasi `scripts/coach.py` menyatukan prepare/checkpoint/complete/status tanpa mengganti pemilihan materi atau penilaian coach. Checkpoint menyimpan input serta provenance sebelum penilaian dan mencoba push. Respons awal/revisi review terpisah, ID tetap saat lanjut/done berulang, dan fase menunggu bukti/review tidak menambah attempt. Jika ringkasan gagal sesudah record tersimpan, hasil tetap dilaporkan tersimpan dan push ditahan; retry memulihkan ringkasan sebelum sinkronisasi, tanpa penilaian ulang. Input langsung pada complete juga disimpan dahulu; jika penilaian ditolak, respons tidak hilang.

Skor total kosong/tanpa sumber ditolak; input belum terverifikasi tidak menutup attempt. Writing parsial/micro-task tanpa band; band Task 1/Task 2 memerlukan sampel lengkap dan empat kriteria, tetap estimasi AI per task. Batas 150/250 kata adalah kebijakan bukti AI konservatif, bukan aturan bahwa examiner tak boleh menilai respons pendek. Speaking transcript/satu bagian tanpa band keseluruhan; pronunciation/estimasi Parts 1–3 memerlukan sumber audio yang benar-benar diperiksa coach. Validator tidak membuktikan sendiri isi screenshot atau pronunciation.

Empat cache resmi dalam coach_refs/ cocok dengan PDF sumber, prompt, source version, halaman/nomor, key, transcript/teks, dan checksum. Paket learner hanya prompt/audio; cache tidak diberikan sebelum done. coach_refs/ masuk whitelist sinkronisasi dengan guard yang sama. Materi historis Judy/furnitur tetap arsip hingga paket siap terverifikasi. Rotasi sementara L–R–S–W memperjelas porsi Writing.

Kesiapan `.local/readiness.json` diikat pada perangkat dan lokasi clone, tidak ikut Git. Observation mempunyai waktu, provenance dan checksum artifact; file yang berubah/deleted memerlukan pemeriksaan ulang. Siap Listening lokal, kontrol player, Speaking terverifikasi, dan aman pindah laptop dilaporkan terpisah. Cache Git hanya historis; aman pindah memerlukan remote baru diperiksa dan folder bersih. Offline bahan lengkap boleh dipakai pada laptop yang sama; dirty+behind diarahkan ke rekonsiliasi tanpa reset/force-push.

Astra (gpt-6-astra) melakukan review dan reproduksi di folder sementara. Finding pemulihan ringkasan dan input unverified yang dapat menutup attempt diperbaiki; checkpoint push dan preservasi input langsung juga diperiksa. Tidak ada blocker kode tersisa pada review terakhir; hasil review tidak menggantikan rehearsal pengguna.

Rehearsal aktual: pengguna menekan Play sendiri dan melaporkan tiga beep pada audio sintetis tiga detik. Laporan tersimpan di evidence/system/2026-10-12-v11-playback-report.json. Chat baru 01a130d0-9882-73c2-b4c6-6e2247a2e09e membaca ID 2026-10-12-listening-1729392fd5b8, satu checkpoint, respons, provenance, evidence, dan kondisi yang sama; bukti di evidence/system/2026-10-12-v11-new-chat-resume.json. Browser bawaan menolak halaman localhost melalui kebijakan browser; audio di chat digunakan untuk uji playback tanpa melewati pembatasan akses. Server sementara telah dihentikan. Audio IELTS baru tidak diputar, screenshot dan rekaman asli belum diterima.

Record rehearsal berjenis system_test dan tidak masuk PROGRESS belajar; skor Tata dan baseline tidak berubah. v1.1 belum commit/push ke GitHub karena plan meminta rehearsal lengkap sebelum publikasi. Repo masih memuat v1 pada commit 73ff2fe95efb93e973ae4940c52ed038ef7da261. Laptop lain belum diperiksa. Setelah screenshot dan rekaman tersedia, coach menyimpan checkpoint/bukti, memeriksa kesiapan secara jujur, menutup rehearsal, lalu menerbitkan dan memverifikasi salinan kedua.

Pengujian akhir: 96 tes berbeda lulus (34 sesi + 21 referensi + 25 wrapper + 16 sinkronisasi). Run gabungan 92 tes dilanjutkan run wrapper final 25 setelah empat kasus tambahan; bukti log di evidence/system/2026-10-12-v11-tests.txt. Astra menjalankan ulang 34 sesi, 21 referensi dan 25 wrapper; catatan penutupan finding di evidence/system/2026-10-12-v11-astra-review.json. Observation lama tanpa checksum kini tidak dapat berstatus siap; perlu pemeriksaan ulang.


## v1.2 — feedback dan adaptasi, 12 Oktober 2026

Permintaan pemilik agar sistem reliable, scalable, dan dapat memperbaiki alur dari feedback disimpan sebagai event asli feedback/2026-10-12-owner-system-design.json, actor owner dan tanpa sinyal preferensi Tata. PROFILE.md dan PROGRESS.md tetap byte-identik terhadap versi Git sebelumnya; tidak ada latihan baru Tata yang selesai atau baseline baru.

Peta sistem ada di SYSTEM.md, kebijakan/kontrak adaptasi di ADAPTATION.md. Satu skill IELTS khusus repo dibuat di .agents/skills/ielts-coach/. SKILL.md merujuk kebijakan serta CLI yang ada, tidak menduplikasi aturan band. Frontmatter YAML/scaffold dan referensi relatif diperiksa memakai parser YAML Ruby serta filesystem; validator Python bawaan telah dicoba tetapi PyYAML tidak tersedia pada interpreter sistem maupun runtime bundled. Tidak memasang dependency. Perilaku skill diperiksa lewat forward test independen Astra dalam folder sementara. Deteksi skill pada laptop lain tetap bagian setup, bukan klaim sudah diuji.

Workflow coach menambah satu operasi feedback, mempertahankan empat operasi v1.1. Prepare/status/complete menghasilkan coaching_brief yang merujuk input sesi, feedback, resolusi, eksperimen/review, versi aturan, preferensi, hipotesis, cakupan skill dan sengketa. Waktu yang dinyatakan saat ini mengalahkan default/preferensi; resume menjaga ID serta alokasi awal attempt. Preferensi hanya dari actor learner dan sinyal eksplisit. Constraint hari ini/sesi ini memakai budget saat itu serta scope sesi, lalu berakhir sesudah sesi selesai; pernyataan global membutuhkan maksud berkelanjutan yang jelas.

Modul adaptation memakai event/ledger append-only dan readback. Retry identik memakai event yang sama, ID sama dengan isi berbeda ditolak. Payload tersimpan diperiksa ulang dan event baru diberi checksum; input sesi stale/invented ditolak. Skor total tidak menghasilkan pola per soal. Dua tugas baru dengan kondisi cukup hanya membentuk hipotesis berulang, bukan kelemahan menetap. Retake, tes sistem, bantuan, kondisi freshness belum diketahui, dan penilaian sengketa dikeluarkan dari analisis kemampuan. Tidak ada training model, server tambahan, scheduler, atau penulisan ulang target/policy otomatis.

Astra meminta pemisahan tiga lapisan: preferensi workflow segera dapat dipakai; hipotesis kemampuan memerlukan bukti baru; skor/target diperiksa dari sumber atau keputusan pengguna. Resolusi confirmed_original memeriksa source/result serta byte bukti asli; perubahan file pada path yang sama membatalkan konfirmasi. correction_required tetap dikarantina tanpa mengubah skor awal. Eksperimen memerlukan sumber yang sebanding untuk keputusan adopted dan tetap dapat inconclusive. Ledger keputusan bukan bukti sebab-akibat atau kenaikan band.

Forward test Astra memakai data fiktif di folder terisolasi: memilih Reading Marie Curie Q1–3, 10 menit; prepare berikutnya memakai ID yang sama; sengketa dan retake dikecualikan; satu attempt layak tidak disebut pola berulang; request owner untuk skor9 tidak mengubah skor; baseline tetap insufficient dan readiness screenshot/rekaman belum terverifikasi. Satu fixture lama menyebut today tetapi diberi scope global; ini dipertahankan sebagai input evaluasi dan mendorong klarifikasi scope pada skill/dokumen, bukan perubahan preferensi nyata Tata. Permintaan baru pada forward test disimpan sebagai scope sesi. Data sesi fiktif tidak disalin ke sessions/ produksi.

Kesiapan operasional dan pedagogis tetap terpisah. Rehearsal asli masih menunggu screenshot dan rekaman pengguna; kontrol beep sintetis serta resume chat baru sudah diperiksa pada v1.1. Belum ada diagnostik baru keempat skill. Versi baru masih lokal dan belum commit/push, mengikuti gate rehearsal dari rencana pengguna. Koordinasi pengembangan penambahan ini memakai tiga subagent (kode, dokumentasi/sync, Astra); saat belajar Tata memakai satu coach utama dan reviewer sesuai kebutuhan. Total modul Python lima, satu skill khusus project, delapan materi awal dan empat referensi koreksi.

Verifikasi akhir v1.2: 130 tes berbeda lulus (34 sesi + 21 referensi + 25 workflow + 7 integrasi adaptasi + 25 adaptasi + 18 Git). Run gabungan 124 dilanjutkan run fokus wrapper/integrasi32 dan adaptasi25 sesudah perbaikan; bukti di evidence/system/2026-10-12-v12-tests.txt. Astra melakukan forward test independen serta rerun adaptasi25; tidak menemukan blocker baru pada perubahan akhir. Eksperimen/review kini mem-pin byte bukti baseline/outcome otomatis; perubahan atau pin hilang menahan adopsi/membatalkan kelayakan bukti keputusan lama. Catatan review: evidence/system/2026-10-12-v12-astra-review.json.


## Sinkronisasi otomatis milestone dan per jam — 12 Oktober 2026

Pengguna memberi instruksi baru untuk sinkronisasi otomatis pada milestone penting, lalu secara eksplisit meminta skill dan scheduled task setiap satu jam. Instruksi terbaru menggantikan penundaan backup sebelum rehearsal lengkap; screenshot/rekaman tetap pending dan tidak dianggap teruji hanya karena berhasil dipush. Riwayat laporan sebelumnya di atas mencerminkan status saat itu.

Skill kedua ielts-github-sync disimpan di .agents/skills/ielts-github-sync/. Helper keenam scripts/hourly_sync.py memvalidasi record sesi/feedback serta cache koreksi, membangun ulang ringkasan dalam session lock, lalu mengambil Git lock untuk sync. Clone bersih diperiksa dan diperbarui fast-forward; perubahan tersimpan dicommit/push ke repo privat main yang diizinkan. Writer atau Git sibuk ditunda; offline/conflict/invalid source mempertahankan data lokal. Tidak ada penilaian ulang, Play, force/reset, credential baru atau perubahan akun. Logger memeriksa pathnya sendiri dan tidak menulis melalui symlink maupun membuat root yang tidak ada.

Heartbeat Codex bernama IELTS GitHub sync tiap jam dibuat ACTIVE lewat automation_update, ID ielts-github-sync-tiap-jam. Target chat lokal saat ini; interval satu jam. Status/target/cadence dibaca ulang dari konfigurasi native dan kartu Scheduled ditampilkan melalui mode view. Jadwal memakai skill khusus dan satu bounded run; kondisi rutin/no change/busy diam, kegagalan atau tindakan baru perlu perhatian. Laptop/Codex harus tersedia untuk folder lokal; skill ikut Git tetapi scheduler/credential tidak otomatis berpindah ke laptop lain.

Coach, helper perjam dan CLI sync langsung memakai urutan session lock lalu Git lock; keduanya nonblocking dan dilepas OS saat proses berhenti. Primitive API Git memakai Git lock saja dan caller yang menulis sesi harus mengambil session lock dahulu. Kegagalan I/O pada lock memberi status terstruktur belum tersinkron. Astra menjalankan probe lintas proses, I/O failure dan symlink-lock di folder sementara; tidak ada blocker tersisa pada review terakhir.

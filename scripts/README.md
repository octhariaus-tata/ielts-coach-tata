# Alat coach

Python 3.8+ dan Git; pustaka standar, tanpa paket tambahan. Tata memakai chat. Script menyimpan catatan dan menjalankan Git; pilihan tugas, pembacaan jawaban dan penilaian tetap pekerjaan coach. Semua path bukti/rujukan relatif terhadap project; untuk folder lain letakkan `--root PATH` **sebelum** subcommand coach/session. Pada Windows gunakan interpreter Python yang sudah diperiksa pada SETUP.md.

## Workflow utama dan feedback

Periksa `python3 scripts/coach.py --help` dan bantuan setiap subcommand sebelum menyiapkan input. Contoh perintah untuk coach:

```sh
python3 scripts/coach.py prepare --task listening-packham-form --kind pilot --minutes 20
python3 scripts/coach.py checkpoint --id SESSION_ID --input .local/checkpoint.json
python3 scripts/coach.py complete --id SESSION_ID --result .local/result.json
python3 scripts/coach.py status
python3 scripts/coach.py status --verify-sync
python3 scripts/coach.py feedback --input .local/feedback.json
```

`SESSION_ID` diganti ID attempt yang dikembalikan alat. `prepare` memeriksa sinkronisasi dan melanjutkan attempt aktif beserta respons tersimpan, tanpa memulai ulang audio atau meminta input lama. Jika belum ada attempt, coach menentukan satu `--task`; waktu eksplisit `--minutes` dipakai dahulu, kemudian preferensi waktu eksplisit Tata yang sesuai scope, lalu default 20 menit. Waktu attempt aktif tidak ditulis ulang ketika resume. Mode `--kind system_test` khusus rehearsal dan tidak dihitung dalam progres. Attempt selesai hanya boleh diulang sebagai review/retake melalui operasi sesi yang sesuai, bukan pengukuran baru.

`checkpoint` menambahkan respons/bukti/kondisi sebelum penilaian, membaca ulang file, lalu mencoba push. `complete` menyimpan hasil yang memenuhi validasi, membaca ulang record, memulihkan ringkasan, dan mencoba push. Input langsung melalui `source_response` disimpan sebagai checkpoint sebelum penilaian; input tetap ada jika penilaian belum memenuhi syarat. Baca **tersimpan** serta **tersinkron** secara terpisah. Jika push gagal setelah hasil tersimpan, gunakan `complete --id SESSION_ID` tanpa `--result` untuk retry sinkronisasi hasil selesai; jangan menilai ulang. `status` biasa membaca keadaan lokal/cache; `--verify-sync` meminta pemeriksaan remote baru. Cache beserta waktu pemeriksaannya tidak membuktikan keadaan jaringan saat ini.

Jika respons/hasil sudah tersimpan tetapi penulisan ringkasan gagal, wrapper melaporkan `saved: true`, `summaries_saved: false`, `synced: false` dan menunda push. Retry checkpoint dengan input identik untuk memperbaiki ringkasan respons, atau `complete --id SESSION_ID` tanpa hasil baru untuk memperbaiki ringkasan hasil selesai. Retry tidak menggandakan revisi, attempt atau penilaian. OS lock membatasi operasi pencatatan serentak pada satu salinan lokal; koordinasi antar perangkat tetap memakai satu laptop aktif dan verifikasi Git.

## Checkpoint dan resume

File JSON sementara disimpan di `.local/`, yang tidak ikut Git. Bentuk contoh berikut adalah **tes sistem**, bukan respons Tata:

```json
{
  "text": "Respons simulasi untuk menguji penyimpanan; bukan jawaban belajar Tata.",
  "evidence": [],
  "conditions": {"actual_minutes": null, "audio_plays": null, "key_seen_before": null},
  "provenance": {"method": "tes sistem", "reference": "rehearsal lokal, bukan attempt Tata"},
  "purpose": "attempt",
  "phase": "awaiting_review"
}
```

Respons dapat berupa `text`, daftar file `evidence/` yang tersedia, `score` dengan `correct`/`total`, atau referensi audio yang dapat ditelusuri. Input memerlukan `provenance.method` dan `provenance.reference`; waktu checkpoint dicatat alat. Jangan memakai angka perkiraan sebagai durasi aktual atau jumlah putaran audio. Bila ada bantuan, catat `conditions.assisted: true` agar penilaian tidak dipakai sebagai inferensi kemampuan/efektivitas/kesiapan. Bukti harus file yang benar-benar ada, bukan path placeholder. Kondisi/fase saja boleh dicatat ketika input belum tersedia.

Fase aktif: `working`, `awaiting_evidence`, atau `awaiting_review`; `completed` diatur ketika hasil lolos. Jika “done” belum memberi jawaban/skor cukup, checkpoint fase menunggu bukti dengan ID yang sama. Jika key/cache tidak dapat diverifikasi, simpan respons dan tunggu review. Revisi setelah feedback memakai `purpose: review`; respons attempt awal tetap tersimpan dan tidak menjadi skor attempt baru. Checkpoint identik tidak menggandakan revisi. Hasil menunjuk `response_revision_id` yang diperiksa coach; revisi review tidak boleh dijadikan respons attempt awal.

`scripts/session.py` tetap menyediakan `start`, `checkpoint --id ID --input PATH`, `finalize --id ID --result PATH`, `status`, dan `rebuild` untuk operasi dasar/pemulihan. `rebuild` memperbarui hanya bagian managed-sessions pada PROGRESS/STATUS, mempertahankan riwayat lama. Record schema 1 lama tetap terbaca; hasil lama tidak otomatis dinilai ulang.

## Hasil dan batas penilaian

Coach menyiapkan `.local/result.json` setelah membaca bukti. Hasil memerlukan respons/skor asli dengan provenance, metode verifikasi, kondisi diketahui dan feedback: satu kekuatan, maksimal dua pola, satu tindakan, serta satu tugas berikutnya. Saat checkpoint sudah ada, gunakan `response_revision_id`; jika belum, `source_response` menyimpan input asli beserta provenance sebelum penilaian.

Contoh **tes sistem** skor total saja; angka ini tidak boleh dipakai sebagai hasil Tata:

```json
{
  "mode": "score_only",
  "scope": "snippet",
  "score": {"correct": 3, "total": 8},
  "verification_method": "laporan simulasi skor total",
  "source_response": {
    "score": {"correct": 3, "total": 8},
    "provenance": {"method": "tes sistem", "reference": "data simulasi lokal, bukan Tata"}
  },
  "answers": [],
  "evidence": [],
  "conditions": {"actual_minutes": null, "audio_plays": null, "key_seen_before": null},
  "feedback": {
    "strength": "Belum dapat menilai kekuatan per soal dari skor total.",
    "patterns": [],
    "action": "Pada tugas baru berikutnya, sertakan screenshot jawaban sebelum meninggalkan halaman.",
    "next_task": "Satu tugas baru sesuai rotasi."
  }
}
```

`score_only`/`reported` memerlukan skor tidak kosong yang cocok dengan skor sumber tersimpan. `unverified` mempertahankan input tanpa skor/band pada fase `awaiting_review`: attempt tetap aktif dan tidak masuk ringkasan latihan selesai. Ketiganya tidak mendukung koreksi jawaban atau pola per soal. Skor total saja tidak membuktikan pilihan jawaban.

`answers_key` memerlukan `key_task_id` yang sama, `key_version_verified: true`, `key_url`, `verification_method`, dan daftar `answers`. Setiap jawaban memuat `number`, `given`, `expected`, `correct` boolean, serta `proof` dari transcript/teks. Skor menghitung bagian yang benar-benar terbaca; screenshot sebagian memakai `scope: partial`. Nomor soal dan URL key harus sesuai snapshot katalog saat attempt dimulai. Key tetap diperiksa coach; alat tidak membuktikan jawaban sendiri. Cuplikan tidak mendapat band. Band perkiraan tes penuh L/R /40 memerlukan 40 nomor pada snapshot, `scope: full`, serta `band_source_url`.

Writing/Speaking memakai `ai_estimate`, `criteria`, `uncertainty` dan sampel tersimpan. Micro-task/parsial Writing mendapat feedback tanpa band; band per task memerlukan `scope: full`, `response_complete: true`, `band_target: task1`/`task2` yang cocok dengan materi, serta empat kriteria: `task_achievement` atau `task_response`, `coherence_cohesion`, `lexical_resource`, `grammatical_range_accuracy`. Kebijakan bukti AI konservatif meminta sampel setidaknya 150/250 kata; respons lebih pendek tetap dapat dibahas, tanpa band dari alat. Ini kebijakan sistem, bukan batas penilaian examiner atau jaminan bahwa jumlah kata saja cukup untuk penilaian. Task 2 saja tidak menjadi band Writing keseluruhan.

Speaking wajib memakai `input_type: transcript`/`audio`. Transcript tidak mendukung pronunciation; isi nilainya null/belum dinilai. Pronunciation memerlukan `audio_inspected: true`, `audio_reference` dan sumber audio tersimpan yang benar-benar diperiksa coach. Band seluruh Speaking memerlukan `scope: full`, `speaking_parts: [1, 2, 3]`, audio memadai, serta kriteria `fluency_coherence`, `lexical_resource`, `grammatical_range_accuracy`, `pronunciation`. Sampel satu bagian hanya mendapat feedback terbatas. Semua band W/S berstatus estimasi AI dengan ketidakpastian, bukan hasil resmi.

Done dengan hasil identik tidak membuat entri ganda. Hasil berbeda pada attempt selesai ditolak; koreksi perlu provenance beralasan, bukan overwrite. Penyimpanan harus dibuktikan dengan membaca ulang record dan ringkasannya sebelum disebut berhasil.

## Referensi offline dan kesiapan

`python3 scripts/references.py` memeriksa empat cache koreksi objektif; gunakan `--task TASK_ID` untuk satu materi. Output pemeriksaan tidak menampilkan jawaban. `coach_refs/` berisi key/transcript/teks Reading terpisah dari prompt/audio Tata. Cache harus cocok dengan source version, halaman/nomor soal, checksum prompt, dan provenance resmi; cache gagal membuat review tertunda. Jangan berikan file cache atau full source PDF kepada Tata sebelum done. Pemeriksaan cache tidak membuktikan playback, jawaban, atau akses hasil browser.

Kesiapan per perangkat ada pada `.local/readiness.json`, terpisah dari catatan bersama. Record memakai ID perangkat dan lokasi folder; menyalin cache ke folder/perangkat lain tidak membuat salinan itu siap. `coach.py status --observe .local/observation.json` mencatat satu observasi dengan format berikut; contoh ini mempertahankan status **belum diuji**, bukan laporan keberhasilan:

```json
{
  "capability": "audio_playback",
  "status": "not_tested",
  "provenance": {"method": "persiapan sistem", "reference": "materials/listening-packham-form.mp3 belum diputar pengguna"},
  "evidence": [],
  "note": "Tunggu pengguna menekan Play sendiri."
}
```

`capability` observasi adalah `audio_playback`, `screenshot_capture`, atau `speaking_audio`. Setiap fitur berstatus `passed`, `failed`, atau `not_tested`, dengan waktu dan asal bukti. Untuk playback `passed`, `provenance.reference` harus **persis path relatif** aset yang dimainkan pengguna, misalnya `materials/listening-packham-form.mp3`; penjelasan laporan pengguna masuk `method`/`note`. Screenshot/Speaking lulus memerlukan gambar/rekaman asli yang telah tersimpan dan diperiksa. Laporan playback suara sintetis hanya membuktikan kontrol yang dites; audio resmi yang belum diputar tetap belum diuji.

Output `ready_local_listening` memerlukan penyimpanan, prompt/audio dan cache koreksi yang utuh, screenshot teruji, serta laporan playback **audio resmi tugas yang dipilih**. `player_controls_verified` dapat lulus dari suara sintetis tanpa membuat Listening resmi siap. `speaking_verified` terpisah dan memerlukan rekaman asli. `safe_switch_laptop` memerlukan remote terbaru terverifikasi, tidak ada commit tertinggal/lebih dahulu, dan tidak ada file lokal pending/asing. Tes kode/file tidak membuktikan pengguna telah memutar audio, mengirim screenshot, atau rekaman berhasil; setiap fitur yang belum diuji tetap `not_tested`.

## Sinkronisasi dan pemulihan

`python3 scripts/sync.py status`, `pull`, atau `push --message "Simpan sesi ID"`. Hanya `status: synced` bersama `remote_verified: true` berarti data coaching sama dengan origin/main pada pemeriksaan itu. `.local/sync.json` hanya cache perangkat ini. Offline/ahead/push gagal berarti belum tersinkron; pertahankan data pada laptop yang sama. Sesi aktif dan respons dapat dipulihkan meski pull terhalang; sebutkan bahwa versi bersama terbaru belum dapat dipastikan.

Whitelist mencakup catatan, bukti, materi dan `coach_refs/`, dengan pemeriksaan credential/symlink yang sama. Jika remote lebih baru dan ada perubahan lokal, coach merekonsiliasi seluruh record/bukti lalu membangun ulang ringkasan sebelum sinkronisasi. Jangan membuat loop push/pull, reset, force-push, atau membuang perubahan. Konflik profil/target yang tidak dapat diputuskan dari bukti perlu klarifikasi.

`feedback/`, `learning/`, `SYSTEM.md` dan `ADAPTATION.md` ikut whitelist. Skill project hanya diizinkan melalui file persis `SKILL.md` serta `agents/openai.yaml` di dua folder: `.agents/skills/ielts-coach/` dan `.agents/skills/ielts-github-sync/`. Folder `.agents/` lain, settings, credential, skill lain dan path yang keluar tetap ditolak; allowlist ini tidak melewati pemeriksaan secret/symlink. `.local/` tetap lokal.

## Autosync milestone dan heartbeat per jam

Pengguna telah mengizinkan push otomatis sesudah checkpoint/hasil/feedback tersimpan dan dibaca ulang, serta setelah materi/pembaruan sistem diverifikasi. Skill `ielts-github-sync` merujuk workflow ini dan runner backup. Tidak ada approval tambahan untuk setiap push dalam repo/branch yang sama setelah autentikasi tersedia; laporan tersinkron tetap memerlukan push dan remote yang terverifikasi. Rehearsal screenshot/rekaman yang belum selesai tidak lagi menahan backup/publikasi, dan tetap dicatat sebagai belum diuji.

Heartbeat Codex setiap 1 jam memanggil satu operasi runner pada laptop aktif ketika aplikasi tersedia:

```sh
python3 scripts/hourly_sync.py --help
python3 scripts/hourly_sync.py --root PATH --message "Backup IELTS Coach Tata"
```

`PATH` diganti folder repo atau hilangkan `--root` untuk default project. Tidak ada argumen action; satu run memvalidasi envelope sesi, feedback dan cache koreksi sebelum memakai sinkronisasi aman. Session/Git lock mencegah interleaving lokal; writer sibuk dapat menghasilkan penundaan, lalu retry pada run berikutnya. Jangan mencoba melewati lock atau mengubah ID untuk membuat backup berhasil.

Status run tersimpan pada `.local/scheduled-sync.json`; credential tetap di luar Git. Tidak ada perubahan berarti tidak perlu commit baru. Run rutin sukses/tanpa perubahan dan busy deferral tetap diam; beri tahu kegagalan atau kebutuhan rekonsiliasi/akses yang baru atau berubah, tanpa mengulang keadaan sama setiap jam. Offline atau credential gagal mempertahankan data sebagai belum tersinkron. Runner hanya menyinkronkan data yang ada: tidak Play/Submit, memberi nilai, menulis ulang aturan, force-push, reset, atau mengubah token/config. Jadwal tidak menjamin run saat laptop tidur/aplikasi tidak tersedia dan tidak menyinkronkan folder laptop lain lewat login Codex.

## Adaptasi dan review

`coach.py feedback --input .local/feedback.json` menyimpan event mentah, membaca ulang dan mencoba sinkronisasi. Input memerlukan ID event, teks, kategori dan provenance, serta actor/scope yang benar. Coach menangkap masukan natural-language tanpa meminta format tambahan dari Tata. Retry identik tidak menambah event; masukan pemilik tidak otomatis menjadi preferensi Tata. Kontrak JSON lengkap dan contoh tes sistem ada pada [ADAPTATION.md](../ADAPTATION.md).

Batas waktu “hari ini/sesi ini” memakai `prepare --minutes` untuk budget saat ini, kemudian event `scope: session` dengan ID baru/aktif; waktu awal attempt aktif tidak ditulis ulang. Preferensi `global` dengan sinyal terstruktur memerlukan maksud berkelanjutan yang eksplisit. Masukan mentah tanpa maksud itu memakai `signals: {}`; modul mengikuti scope input, tanpa parser bahasa alami untuk menentukan durasinya.

`prepare`, `status`, `complete` dan operasi feedback mengembalikan `coaching_brief`: preferensi eksplisit yang relevan, maksimal dua hipotesis sesuai skill tugas, peringatan penilaian dikecualikan, cakupan skill/kesiapan, versi aturan dan ID input. Coach memeriksa brief sebelum menyesuaikan penugasan; alat memberi rekomendasi, tanpa menilai ulang skor atau mengubah aturan project. `status` tetap membaca lokal kecuali `--verify-sync` diminta.

`scripts/adaptation.py` menyediakan `record-feedback --input PATH`, `analyze`, `experiment --input PATH`, `review-experiment --id ID --input PATH` dan `resolve-feedback --id ID --input PATH`; `--root PATH` berada sebelum subcommand. Raw feedback serta resolusi tetap ada pada `feedback/`; ledger eksperimen/review ada pada `learning/`. Analisis turunan dihitung ulang dari input mentah, dengan versi aturan dan ID sumber pada output. Tes sistem, retake/key terlihat, latihan dengan bantuan, bukti skor total untuk pola per soal, dan sengketa penilaian terbuka tidak membentuk perkembangan kemampuan. Dua tugas baru yang layak hanya menghasilkan hipotesis → drill → cek transfer baru. Preferensi eksplisit Tata dapat langsung dipakai tanpa menyimpulkan kemampuan.

Review eksperimen dapat berakhir `inconclusive` bila baseline/outcome belum cukup. Resolusi penilaian harus menyertakan sumber pemeriksaan; `confirmed_original` mengikat hash sumber/hasil dan file bukti asli secara otomatis, sehingga perubahan byte atau file yang hilang membuat resolusi basi. `correction_required` tetap dikarantina dan versi ini tidak membuat overlay koreksi otomatis. Review Astra dipanggil sesuai kebutuhan; penambahan agent tidak menggantikan bukti atau pemeriksaan sumber. Skill khusus project merujuk workflow di sini serta AGENTS, SYSTEM dan ADAPTATION; lihat discovery pada SETUP.md.

## Pemeriksaan

`python3 -m unittest discover -s tests -v`

Data tes dibuat di folder sementara dan berlabel simulasi; tidak menjadi skor Tata. Rehearsal pengguna memerlukan Play oleh pengguna sendiri, screenshot contoh, rekaman pendek, serta resume chat baru; jangan menyebutnya lulus hanya berdasarkan tes otomatis.

## Teacher packets and teaching lessons v1.3

One main coach voice delegates one read-only Teacher packet preparation through the project-local ielts-teacher skill. `agents/openai.yaml` is discovery metadata, not a permanently running agent. Main coach checks the returned JSON and all examples/answers; learner projections are structurally separated from `coach_only`. Main coach must also check semantic leaks, which JSON validation alone cannot prove.

Use `python3 scripts/coach.py lesson --help` first. All paths in inputs are relative to this project; temporary input files live in .local/. Operations:

- `lesson teacher-brief --input .local/goal.json`: goal fields main_skill, ielts_task_type, objective. Returns sanitized effective preferences and packet contract; no correction keys.
- `lesson packet --input .local/packet.json --defer-sync`: register immutable packet. Schema is `lessons.validate_packet`: schema_version 1, id/version/role primary or backup/main_skill/ielts_task_type/objective/source_label coach_created or official/practice_kind short_drill or task/theory/strategy/worked_example(prompt,answer,reasoning)/guided/independent/coach_only/basis/provenance. Items: id,prompt, optional flag; guided only may carry hint. Short drills have 20–30 independent items. `basis` pins preferences_sha256 from the brief and relevant file SHA256s in files; no coach_refs inputs. Official packets reference official_task_id and pin exact learner prompt, retain catalog question IDs, and omit official answers.
- `lesson prepare`: resume active work or start valid primary packet; `--minutes` applies only to new lessons. `prepare` also resolves teaching lessons before creating IELTS attempts. Fresh source/preference changes mark prepared packets stale. `lesson retire-packet --id ID --input .local/reason.json` preserves old packet and records reason/provenance before registering its replacement.
- `lesson present --id ID --input .local/display.json`: provenance required; optional item_ids selects what is actually shown. Use returned learner content unchanged and record it at delivery. Counts distinguish pool from displayed items. Main coach displays one clearly numbered list after guided review; unused optional items are not debt. For an official independent stage, this wrapper preflights and links the official attempt before displaying its prompt.
- `lesson checkpoint --id ID --input .local/response.json`: text/answers mapping item ID to string/evidence/provenance and submission partial, complete or paused; optional purpose attempt/review and conditions. Coach determines completeness from conversational evidence, not correctness or literal done. Complete may include intentional blanks or a final time-limited subset; label the reviewed scope honestly. Explicit pauses/partial responses are never reviewed. Raw first answers persist before assessment.
- `lesson review --id ID --input .local/review.json`: response_id, submitted item_ids, provenance, feedback(strength,patterns at most2,action,next_task); optional criteria grammar/spelling/punctuation/task_fulfilment as text or {correct,total,notes}. No band/pronunciation/mastery estimate. Linked official result may be cited by official_result_reference only after `coach.py complete` validates it; lesson never copies official score.
- `lesson advance --id ID --input .local/stage.json`: stage and provenance; follows theory/example/guided/independent/review/completed. Show theory/example and checkpoint/review guided/independent first. Explicit learner-requested skip requires learner_requested_skip true, actor learner and provenance; never infer skip from impatience alone. `lesson complete` is advance to completed after review, not a regrade.
- `lesson inspect [--id ID]`: safe current stage, prompt, response references and counts. No private keys. Use natural completion: do not repeatedly ask for done on a clearly complete set; partial/pause still waits.
- `lesson migrate --input .local/migration.json`: coach recovery only, packet_id, exact pending stage, provenance and existing references. Original legacy budget is null when unknown; do not create historical synthetic responses/displays. Earlier teaching is referenced, pending prompt is pinned. Existing official attempts and raw evidence stay byte-identical.

Lesson state is in learning/lessons, immutable packets in learning/packets. One primary and one backup prepared at a time; retired packets retained under learning/packet-retirements. Active unlinked lesson plus official attempt, or multiple active records, requires reconciliation. Startup never silently replaces work. Official material preflight still happens at assignment; prepare opens an official attempt only when its linked lesson reaches independent stage.

By default each mutation attempts existing safe milestone sync. `--defer-sync` saves/reads back locally and explicitly returns synced false, sync_pending true; use it to group teaching bookkeeping into one same-lesson milestone, then run hourly_sync. Report teaching first and routine bookkeeping quietly. .local/implementation-pending.json is a local validation hold during authorized system implementation; backup defers without publishing intermediate edits until the implementer removes the marker after checks. A stale marker requires explicit verification/recovery, not automatic expiry. No new automation is created.

For ordinary responses within an active lesson, use the verified packet and known ID, local `lesson checkpoint/review/advance/present --defer-sync` as applicable, then synchronize at a stage boundary, pause or completion. Avoid repeating `prepare` (which pulls), readiness/progress inventories, broad searches or agent preparation per answer. Each response remains durably checkpointed and read back before grading. This removes avoidable network/setup work between answers; it does not establish an end-to-end latency improvement until real sessions are measured.

Structured learner preference scope lesson uses a real lesson_id. Only active scope applies; completed scopes expire. 40 minutes is the new learner global budget, not a new IELTS test-duration rule. 5/5/8/17/5 is a planning estimate only. Teacher packet validation and system tests do not prove a learner band, audio playback or readiness.

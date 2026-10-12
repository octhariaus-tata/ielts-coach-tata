# Alat coach

Python 3.8+ dan Git; tanpa paket tambahan. Tata menggunakan chat, bukan perintah ini.

## Mulai / lanjut

`python3 scripts/session.py start --task listening-packham-form --skill Listening --kind pilot --minutes 20`

Alat mengembalikan ID baru, atau sesi aktif dengan tugas yang sama. Sesi aktif lain harus dilanjutkan/diselesaikan dahulu. Tugas yang sudah selesai hanya dapat dimulai lagi dengan kind `retake`; untuk pengukuran baru pilih materi baru. Status: `python3 scripts/session.py status`. Untuk folder lain, letakkan `--root PATH` **sebelum** subcommand.

## Done

Coach mengisi `.local/result.json` setelah membaca jawaban dan key. Jalankan `python3 scripts/session.py finalize --id ID --result .local/result.json`. File input sementara tidak masuk Git. Hasil tersimpan di sessions/; PROGRESS dan STATUS diperbarui hanya di dalam marker managed-sessions. `rebuild` memulihkan ringkasan tanpa mengubah riwayat.

Bentuk minimal untuk skor total saja:

```json
{
  "mode": "score_only",
  "scope": "snippet",
  "score": {"correct": 3, "total": 7},
  "verification_method": "screenshot skor total",
  "answers": [],
  "evidence": ["evidence/ID-score.png"],
  "conditions": {"actual_minutes": null, "audio_plays": null, "key_seen_before": null},
  "feedback": {
    "strength": "Belum dapat menilai kekuatan per soal dari skor total.",
    "patterns": [],
    "action": "Pada tugas baru berikutnya, sertakan screenshot jawaban sebelum meninggalkan halaman.",
    "next_task": "Satu tugas baru sesuai rotasi."
  }
}
```

`mode=answers_key` memerlukan `key_task_id` sama dengan tugas sesi, `key_version_verified=true`, `key_url`, `verification_method`, serta array `answers`. Setiap jawaban memuat `number`, `given`, `expected`, `correct` (boolean), dan `proof` dari transcript/teks. Skor hanya menghitung array tersebut; screenshot sebagian memakai scope `partial`. `start` menyimpan snapshot katalog; nomor/total soal dan URL key harus sesuai snapshot itu. Key tetap diperiksa coach terhadap sumber; alat tidak menggantikan pembacaan sumber.

`reported` dan `unverified` tidak boleh diberi pola per soal. Cuplikan tidak boleh diberi band. Tes penuh L/R /40 memerlukan 40 nomor soal pada snapshot, scope `full` dan `band_source_url`; tetap band perkiraan. W/S menggunakan `ai_estimate`, kriteria IELTS, `uncertainty`, serta bukti sampel. Speaking wajib mempunyai input_type `transcript` atau `audio`. Dari transcript, pronunciation null/belum dinilai. Nilai pronunciation memerlukan audio_inspected true dan audio_reference yang benar-benar diperiksa coach. Maksimal dua pola kesalahan, satu tindakan, satu tugas berikutnya.

Done dengan hasil identik tidak membuat catatan ganda. Hasil berbeda pada sesi selesai ditolak; koreksi perlu catatan provenance beralasan, bukan overwrite diam-diam.

## Sinkronisasi

`python3 scripts/sync.py status`, `pull`, atau `push --message "Simpan sesi ID"`. Baca JSON keluarannya. Hanya `synced` berarti data coaching bersih dan sama dengan origin/main pada pemeriksaan itu. Cache .local/sync.json hanya berlaku di perangkat ini. Offline/ahead/push gagal berarti belum tersinkron; pertahankan data dan jangan pindah laptop.

## Pemeriksaan

`python3 -m unittest discover -s tests -v`

Semua data tes dibuat di folder sementara dan berlabel simulasi. Tidak menjadi skor Tata.

# Adaptasi dari feedback dan bukti belajar

Sistem memperbaiki pilihan tugas dan cara memberi feedback dari catatan yang dapat ditelusuri. **Data mentah tetap disimpan; analisis memberi rekomendasi untuk coach.** Model tidak dilatih ulang dan modul tidak mengganti aturan, target, profil, jawaban atau skor. Aturan di bawah adalah kebijakan program ini, bukan bukti bahwa peningkatan band pasti terjadi.

## Input dan batas penggunaannya

| Input | Penggunaan yang diizinkan |
| --- | --- |
| Preferensi eksplisit Tata | Waktu yang tersedia dan gaya feedback dapat dipakai segera dalam scope yang diminta; tidak memerlukan dua attempt |
| Masukan Suk/pemilik atau actor belum jelas | Disimpan sebagai masukan/desain; tidak otomatis menjadi preferensi Tata |
| Kendala akses | Menentukan tindakan perbaikan alur; tidak berarti kemampuan IELTS lemah dan tidak membuktikan kesiapan perangkat lain |
| “Terlalu sulit/mudah” | Dicatat sebagai pengalaman; coach membandingkan dengan hasil baru, tanpa menyimpulkan band dari keluhan saja |
| Pola pada jawaban terverifikasi | Minimal dua attempt dengan tugas baru berbeda dapat membentuk hipotesis untuk drill dan pemeriksaan transfer; belum kelemahan menetap |
| Hanya skor total | Tren umum dengan label bukti; tidak mendukung pola per soal |
| Sengketa penilaian belum diselesaikan | Penilaian terkait dikarantina dari seluruh analisis kemampuan sampai sumber diperiksa; asal dan skor awal dipertahankan |
| Retake/key telah terlihat, bantuan, atau tes sistem | Review/tes alur; tidak menjadi bukti perkembangan atau outcome kemampuan independen |

Hipotesis selalu menyebut skill, pola, ID input dan alasan. Untuk inferensi kemampuan, key harus tercatat belum terlihat; Listening harus tercatat satu kali putar. Jika bantuan memang diberikan, catat flag kanonis `conditions.assisted: true`; penilaian itu dikecualikan dari inferensi kemampuan, outcome eksperimen dan kesiapan. Kondisi freshness yang belum diketahui dikecualikan dari inferensi, bukan ditebak. Hipotesis pola tidak selalu memerlukan attempt berwaktu, sedangkan kesiapan tes memerlukan kondisi berwaktu. Dua attempt adalah ambang untuk mengajukan drill, bukan bukti statistik atau diagnosis kelemahan permanen. Setelah drill, coach memeriksa transfer pada materi resmi baru. Jika bukti belum cukup, pertahankan rotasi L–R–S–W dan minta bukti yang relevan saat tersedia; jangan membuat baseline dari trial teknis.

## Catatan yang disimpan

`feedback/` menyimpan event mentah dengan ID, teks, kategori, actor, scope, provenance dan waktu. Event tidak ditimpa; retry ID/input yang sama harus idempotent, dan pembetulan memakai event pemeriksaan baru. Resolusi ada pada `feedback/resolutions/`; ledger eksperimen dan keputusan ada pada `learning/experiments/` serta `learning/reviews/`. Analisis turunan dihitung ulang dari record mentah, bukan cache yang menimpa asal data. Output menyertakan `rule_version`, `input_session_ids`, `input_feedback_ids`, `input_resolution_ids`, status pengecualian dan alasan supaya rekomendasi dapat diaudit dan dibangun ulang.

Kategori masukan adalah `preference`, `access`, `difficulty`, atau `scoring_dispute`. `actor` adalah `learner`, `owner`, atau `unspecified`; default tidak jelas tidak boleh diasumsikan Tata. `scope` adalah `global` atau `session`, dengan `session_id` bila terkait attempt. **Sengketa skor wajib memakai `scope: session` dan ID attempt tertentu**; permintaan umum agar sistem lebih dapat dipercaya tetap masukan desain, bukan sengketa skor global. `kind: system_test` memisahkan simulasi dari data pelajar. `provenance.method` dan `provenance.reference` wajib menunjuk pesan, tool atau bukti yang benar-benar tersedia. Jangan menafsirkan teks bebas menjadi sinyal terstruktur tanpa maksud eksplisit pengguna.

Preferensi terstruktur menerima `preferred_feedback_style: concise|detailed` serta `available_minutes` 1–180. Pengalaman kesulitan menerima `difficulty: too_easy|too_hard|appropriate`. Hanya sinyal eksplisit dari `actor: learner` dapat menjadi preferensi efektif. Batas waktu adalah waktu yang dinyatakan pengguna, bukan waktu aktual yang sudah dipakai. Masukan pemilik mengenai arsitektur tidak menambah progres atau mengubah kemampuan Tata.

**“Hari ini/sesi ini cuma punya 10 menit” berlaku untuk sesi itu.** Coach memakai `prepare --minutes 10` untuk budget saat ini, lalu mencatat masukan dengan `scope: session` dan ID attempt baru/aktif. Resume tetap mempertahankan waktu awal pada record attempt. Sinyal terstruktur `scope: global` hanya dipakai jika pengguna secara eksplisit menginginkan preferensi berkelanjutan; batas waktu hari ini tidak diteruskan ke semua sesi. Masukan umum boleh disimpan mentah lebih dahulu dengan `signals: {}` tanpa menebak preferensi permanen. Modul mengikuti scope JSON yang diberikan coach; modul tidak menafsirkan frasa waktu secara otomatis.

## Cara coach memakai modul

Tata cukup memberi feedback dalam chat, misalnya “feedback-nya kepanjangan” atau “hari ini cuma punya 10 menit”. Coach menyimpan teks asli dan scope yang jelas; JSON serta perintah berikut adalah pekerjaan coach. Periksa bantuan modul sebelum mengisi input:

```sh
python3 scripts/adaptation.py --help
python3 scripts/adaptation.py record-feedback --input .local/feedback.json
python3 scripts/adaptation.py analyze
python3 scripts/adaptation.py experiment --input .local/experiment.json
python3 scripts/adaptation.py review-experiment --id EXPERIMENT_ID --input .local/review.json
python3 scripts/adaptation.py resolve-feedback --id FEEDBACK_ID --input .local/resolution.json
```

Untuk folder lain gunakan `--root PATH` sebelum subcommand. File input sementara ada pada `.local/`, sedangkan event serta ledger yang tersimpan disinkronkan melalui whitelist project. Coach membaca ulang hasil penyimpanan sebelum menyatakan berhasil. Jika sinkronisasi gagal, hasil lokal tetap ada; sebutkan belum tersinkron dan lanjutkan pada laptop yang sama.

Contoh berikut hanya **tes sistem**, bukan preferensi Tata:

```json
{
  "event_id": "system-test-feedback-example",
  "kind": "system_test",
  "actor": "learner",
  "category": "preference",
  "scope": "global",
  "text": "Contoh simulasi: untuk sesi-sesi berikutnya gunakan feedback singkat dan waktu 10 menit.",
  "signals": {"preferred_feedback_style": "concise", "available_minutes": 10},
  "provenance": {"method": "tes sistem", "reference": "contoh dokumentasi, bukan laporan Tata"}
}
```

Untuk data asli, gunakan ID event unik dan provenance pesan yang nyata. Jangan mengubah `kind` contoh lalu mengakuinya sebagai preferensi yang telah dinyatakan Tata. Jika scope sesi, `session_id` harus cocok dengan stream sesi learner/tes sistem. Laporan `analyze` memuat `preferences`, `unresolved_disputes`, `access_issues`, `recurring_hypotheses`, `excluded_assessment_ids`, `exclusion_reasons`, `coverage`, `next_skill` dan `readiness`. Coach memeriksa alasan serta input sebelum mengubah penugasan; laporan tidak menilai ulang jawaban.

## Sengketa penilaian

Simpan pernyataan pengguna sebagai `scoring_dispute`, lalu periksa respons asli, versi key/transcript atau kriteria, dan bukti penilaian. Tidak cukup untuk sekadar mengganti angka atau menulis “sudah benar”. Resolusi menerima `confirmed_original` atau `correction_required`, dengan `rationale` dan provenance sumber pemeriksaan; bukti tersedia disimpan dalam `evidence/`.

`confirmed_original` memerlukan sumber asli attempt tertentu yang dapat diperiksa ulang; modul menyimpan hash sumber/hasil serta checksum byte file bukti asli yang tersedia secara otomatis, termasuk bukti sumber yang tidak disebut ulang dalam input resolusi. Perubahan atau hilangnya file membatalkan konfirmasi lama; path/JSON yang masih sama tidak cukup. `correction_required` tetap dikarantina dari analisis kemampuan sampai prosedur koreksi beralasan diselesaikan. Versi ini belum memberi overlay skor koreksi otomatis. Jangan menimpa hasil lama atau menghapus masukan awal. Jika sumber belum cukup, pertahankan sengketa terbuka dan minta bukti yang relevan, tanpa menebak skor benar.

## Eksperimen dan keputusan

Eksperimen mencatat `event_id`, `hypothesis`, `proposed_change`, `metric`, dan provenance. Scope perubahan adalah `presentation` atau `workflow`; ukuran yang tersedia `response_capture`, `completion`, `transfer_accuracy`, atau `feedback_usefulness`. Baseline menyebut `baseline_session_ids`, serta bukti yang tersedia. Baseline kosong boleh disimpan secara jujur sebagai belum tersedia; itu bukan dasar klaim keberhasilan.

Review mencatat `decision: adopted|rejected|inconclusive`, `rationale`, `session_ids`, provenance dan bukti. Untuk keputusan learner `adopted`, diperlukan baseline nyata dan minimal dua outcome independen dari tugas baru berbeda yang sebanding: skill, jenis soal dan scope sama, kondisi berwaktu/key serta audio bila relevan dicatat, serta tidak disengketakan, dibantu, retake atau tes sistem. Ini pemeriksaan bukti untuk keputusan coach, bukan pembuktian sebab-akibat.

Coach boleh langsung mengikuti preferensi Tata tanpa menjadikannya eksperimen kemampuan. Eksperimen kecil cocok untuk perubahan alur yang belum jelas manfaatnya, misalnya cara menangkap respons. Jika data tidak memadai atau tidak sebanding, gunakan `inconclusive`; jangan memaksakan berhasil/gagal. Ledger mencatat alasan serta input IDs. Keputusan eksperimen tidak menulis ulang `AGENTS.md`, target, profil atau skor secara otomatis. Prinsip log, evaluasi khusus tugas dan kalibrasi manusia mengikuti [panduan eval OpenAI](https://developers.openai.com/api/docs/guides/evaluation-best-practices); ambang bukti di sini adalah kebijakan lokal.

Indikator kesiapan belajar juga konservatif: minimal dua materi baru dengan hasil penuh yang layak per skill; Writing memerlukan cakupan Task 1 dan Task 2, masing-masing dua sampel berbeda. Listening/Reading penuh memakai /40; Writing/Speaking memakai sampel lengkap yang memenuhi kebijakan bukti. Kondisi tes dicatat, dan sengketa terbuka menahan pemeriksaan kesiapan. Output yang cukup hanya `coach_review_required`, bukan prediksi band, sertifikat kesiapan atau bukti telah mencapai target. Skor tetap diperiksa coach; aturan jumlah sampel ini merupakan trigger lokal untuk review.

## Patokan pemeriksaan

- Feedback mentah/provenance tetap dapat dibaca; retry tidak menggandakan event dan scope sesi tidak bocor menjadi preferensi global.
- Masukan owner/actor tidak jelas, tes sistem, skor total dan retake tidak menjadi dugaan kelemahan Tata.
- Dua tugas baru yang layak dapat menghasilkan hipotesis yang menyebut sumber; satu attempt atau dua pengulangan tugas yang sama tidak cukup.
- Sengketa terbuka menahan seluruh penilaian terkait dari analisis kemampuan, tanpa mengganti skor awal.
- Eksperimen tanpa baseline/outcome sebanding tidak dapat dianggap `adopted`; `inconclusive` tetap hasil yang sah.
- Data adaptasi ikut repo privat; credential, pengaturan akun, kesiapan perangkat dan skill lain tetap di luar whitelist.

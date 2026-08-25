# Gerçek Soru Değerlendirmesi

Değerlendirme `tests/documents/` içindeki `Mole Concept.pdf` ve `W2-The Mole.pdf` belgeleri üzerinde yapıldı. Test betiği temiz ve geçici bir SQLite veritabanı oluşturdu; PDF'leri sırasıyla 10 ve 5 parça olarak otomatik indeksledi. `RAG_BACKEND=foundry` zorunlu olarak seçildi; embedding için `qwen3-embedding-0.6b`, yanıt üretimi için `phi-3.5-mini` kullanıldı. Modeller önceden belleğe yüklendi ve her soru ayrı ayrı süre ölçülerek çalıştırıldı.

Başarı ölçütü cevaplanabilir sorularda beklenen bilginin ve en az bir kaynağın bulunmasıdır. Cevaplanamaz sorularda yanıtın tam olarak `Bu bilgi yüklenen belgelerde bulunmuyor.` olması beklenmiştir.

| # | Soru | Beklenti | Süre | Sonuç | Alınan yanıt |
| 1 | Avogadro sayısının değeri nedir? | Cevaplanabilir | 5,01 sn | Başarılı | 6.02 x 10^23, Avogadro sayısının değeri [1]. |
| 2 | STP koşullarında bir mol gaz kaç litre hacim kaplar? | Cevaplanabilir | 4,54 sn | Başarılı | 22.4 L [2] |
| 3 | STP koşullarında sıcaklık ve basınç nedir? | Cevaplanabilir | 5,54 sn | Başarılı | STP koşullarında sıcaklık 0 ºC veya 273K ve basınç 1 atm'dir [2] |
| 4 | Belgeye göre TNT'nin ampirik formülü nedir? | Cevaplanabilir | 2,41 sn | Başarılı | C7H5N3O6 [1] |
| 5 | Gümüşün molar kütlesi kaç g/mol'dür? | Cevaplanabilir | 3,72 sn | Başarılı | 108.0 g/mol [1] |
| 6 | C2X4 sorusunda X elementinin molar kütlesi kaçtır? | Cevaplanabilir | 3,96 sn | Başarılı | 19.0 g/mol [1], [2] |
| 7 | MgSO4.xH2O hidratı sorusunda x kaçtır? | Cevaplanabilir | 2,29 sn | Başarılı | x=7 [1] |
| 8 | Suyun kaynama noktası kaç derecedir? | Cevaplanamaz | 0,05 sn | Başarılı | Bu bilgi yüklenen belgelerde bulunmuyor. |
| 9 | Bu belgelerin yazarı kimdir? | Cevaplanamaz | 0,04 sn | Başarılı | Bu bilgi yüklenen belgelerde bulunmuyor. |
| 10 | Fransa'nın başkenti neresidir? | Cevaplanamaz | 0,06 sn | Başarılı | Bu bilgi yüklenen belgelerde bulunmuyor. |

## Özet

- Başarılı sonuç: **10/10**
- Cevaplanabilir sorular: **7/7**
- Cevaplanamaz sorular: **3/3**
- Otomatik indekslenen parçalar: **15**
- Ortalama yanıt süresi: **2,76 saniye**

Değerlendirmeyi yeniden çalıştırmak için:

```bash
python tests/evaluate_rag.py
```

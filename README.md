# Belge Soru-Cevap

Bu proje, yüklediğiniz PDF, TXT ve Markdown dosyaları hakkında soru sorabileceğiniz küçük bir web uygulaması. Belgeyi parçalara ayırıyor, ilgili bölümleri buluyor ve yanıtı yalnızca bu bölümlere dayanarak hazırlıyor. İşlem Foundry Local ile bilgisayarın üzerinde çalışıyor; model kullanılırken belgeler bir bulut servisine gönderilmiyor.

## Gerekenler

- Python 3.11 veya daha yeni bir sürüm
- En az 8 GB RAM
- İlk model indirmeleri için internet bağlantısı
- Windows, macOS veya Linux

## 1. Foundry Local kurulumu

macOS:

```bash
brew tap microsoft/foundrylocal
brew install foundrylocal
```

Windows:

```powershell
winget install Microsoft.FoundryLocal
```

Kurulumdan sonra terminali yeniden açın ve kontrol edin:

```bash
foundry --version
```

Ayrıntılı ve güncel kurulum seçenekleri için [Microsoft Foundry Local başlangıç rehberine](https://learn.microsoft.com/en-us/azure/foundry-local/get-started) bakabilirsiniz.

## 2. Python ortamı ve paketler

Proje klasöründe bir terminal açın.

macOS veya Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Uygulamayı başlatma

Foundry ile çalıştığından emin olmak için backend'i açıkça seçin.

macOS veya Linux:

```bash
RAG_BACKEND=foundry python app.py
```

Windows PowerShell:

```powershell
$env:RAG_BACKEND="foundry"
python app.py
```

Sonra tarayıcıdan `http://127.0.0.1:8000` adresini açın. İlk çalıştırmada modeller indirileceği ve belleğe yükleneceği için açılış normalden uzun sürebilir. Sonraki sorular daha hızlı yanıtlanır.

`RAG_BACKEND=foundry` seçiliyken Foundry Local başlatılamazsa uygulama hata verir; sessizce basit arama moduna geçmez.

## Kullanılan modeller

- `qwen3-embedding-0.6b`: Belgeleri ve soruları sayısal vektörlere dönüştürür.
- `phi-3.5-mini`: Bulunan belge parçalarından kısa Türkçe yanıt üretir.

Model adları `RAG_EMBED_MODEL` ve `RAG_CHAT_MODEL` ortam değişkenleriyle değiştirilebilir.

## Nasıl kullanılır?

1. PDF, TXT veya Markdown dosyanızı seçin.
2. **İndeksle** düğmesine basın.
3. Dosya belge listesinde göründükten sonra sorunuzu yazın.
4. Yanıtın altındaki kaynak bölümünden kullanılan belgeyi kontrol edin.

## Testler

Kod testleri modeli yüklemeden çalışır:

```bash
RAG_BACKEND=local python -m unittest discover -s tests -v
```

Gerçek Foundry modelleriyle 10 soruluk değerlendirme:

```bash
python tests/evaluate_rag.py
```

`tests/documents/` klasöründeki iki örnek PDF test sırasında geçici bir veritabanına otomatik olarak indekslenir. Uygulamanın `data/rag.db` dosyası kullanılmaz veya değiştirilmez. Son değerlendirme çıktısı `TEST_RESULTS.md` dosyasında bulunur.

## Proje yapısı

- `app.py`: Web sunucusu ve API adresleri
- `rag/core.py`: Metin çıkarma, parçalama, arama ve yanıt üretme
- `web/`: Kullanıcı arayüzü
- `tests/`: Kod testleri, değerlendirme betiği ve test PDF'leri
- `data/rag.db`: İndekslenen belge parçaları ve embedding verileri
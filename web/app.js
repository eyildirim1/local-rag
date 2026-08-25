const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#file-input");
const uploadButton = document.querySelector("#upload-button");
const uploadMessage = document.querySelector("#upload-message");
const documentList = document.querySelector("#document-list");
const clearButton = document.querySelector("#clear-button");
const questionForm = document.querySelector("#question-form");
const questionInput = document.querySelector("#question");
const sendButton = document.querySelector("#send-button");
const messages = document.querySelector("#messages");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function setUploadMessage(text, type = "") {
  uploadMessage.textContent = text;
  uploadMessage.className = type;
}

function renderDocuments(documents) {
  if (!documents.length) {
    documentList.innerHTML = '<p class="muted">Henüz belge eklenmedi.</p>';
    return;
  }

  documentList.innerHTML = documents.map(document => `
    <div class="document-row">
      <span title="${escapeHtml(document.source)}">${escapeHtml(document.source)}</span>
      <small>${document.chunk_count} parça</small>
    </div>
  `).join("");
}

async function readJson(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("Sunucudan geçersiz yanıt alındı.");
  }
}

async function loadDocuments() {
  const response = await fetch("/api/documents", { cache: "no-store" });
  const result = await readJson(response);
  if (!response.ok) throw new Error(result.error || "Belgeler alınamadı.");
  renderDocuments(result.documents || []);
}

uploadForm.addEventListener("submit", async event => {
  event.preventDefault();
  const form = uploadForm;
  const files = Array.from(fileInput.files || []);

  if (!files.length) {
    setUploadMessage("Önce bir dosya seçin.", "error");
    return;
  }

  const invalid = files.find(file => !/\.(pdf|txt|md)$/i.test(file.name));
  if (invalid) {
    setUploadMessage(`${invalid.name} desteklenmiyor.`, "error");
    return;
  }

  uploadButton.disabled = true;
  uploadButton.textContent = "İşleniyor...";
  setUploadMessage("Belge yükleniyor ve indeksleniyor...");

  try {
    const formData = new FormData(form);
    const response = await fetch("/api/ingest", { method: "POST", body: formData });
    const result = await readJson(response);
    if (!response.ok) throw new Error(result.error || "Belge yüklenemedi.");

    form.reset();
    renderDocuments(result.documents || []);
    const chunks = result.indexed.reduce((total, item) => total + item.chunks, 0);
    setUploadMessage(`${result.indexed.length} belge, ${chunks} parça olarak eklendi.`, "success");
  } catch (error) {
    setUploadMessage(error.message, "error");
    await loadDocuments().catch(() => {});
  } finally {
    uploadButton.disabled = false;
    uploadButton.textContent = "İndeksle";
  }
});

clearButton.addEventListener("click", async () => {
  if (!window.confirm("Eklenen tüm belgeler silinsin mi?")) return;
  const response = await fetch("/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}"
  });
  const result = await readJson(response);
  if (!response.ok) {
    setUploadMessage(result.error || "Belgeler silinemedi.", "error");
    return;
  }
  renderDocuments([]);
  setUploadMessage("Belgeler silindi.", "success");
});

function addMessage(type, content, sources = []) {
  document.querySelector("#empty-message")?.remove();
  const element = document.createElement("div");
  element.className = `message ${type}`;
  const sourceHtml = sources.length ? `<div class="sources">${sources.map(source => `
    <div><strong>${escapeHtml(source.name)}</strong><p>${escapeHtml(source.excerpt)}...</p></div>
  `).join("")}</div>` : "";
  element.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>${sourceHtml}`;
  messages.append(element);
  messages.scrollTop = messages.scrollHeight;
  return element;
}

questionForm.addEventListener("submit", async event => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  addMessage("user", question);
  questionInput.value = "";
  sendButton.disabled = true;
  const pending = addMessage("assistant", "Belgelerde aranıyor...");

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 3 })
    });
    const result = await readJson(response);
    if (!response.ok) throw new Error(result.error || "Yanıt alınamadı.");
    pending.remove();
    addMessage("assistant", result.answer, result.sources || []);
  } catch (error) {
    pending.querySelector(".bubble").textContent = error.message;
  } finally {
    sendButton.disabled = false;
  }
});

loadDocuments().catch(error => {
  documentList.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
});

/**
 * Frontend LeafSearch: điều hướng, upload, đọc REST API và hiển thị dữ liệu THẬT.
 * Không chứa dữ liệu giả/điểm đánh giá dựng sẵn.
 * Xem docs/FILE_GUIDE.md trước khi sửa.
 */

const API = '/api';
const GROUPS = ['color', 'shape', 'ridge', 'texture'];
const DEFAULT_WEIGHTS = { color: 25, shape: 45, ridge: 15, texture: 15 };
const $ = (selector) => document.querySelector(selector);
const byId = (id) => document.getElementById(id);
const state = { selectedFile: null, previewUrl: null, groups: [], activeGroup: null, page: 1, images: [], ready: false };

/** Chặn HTML injection khi đưa tên file/mã nhóm từ API vào template. */
function safe(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
}
function formatNumber(n) { return Number(n ?? 0).toLocaleString('vi-VN'); }
function percent(n) { return `${(100 * Number(n ?? 0)).toFixed(2)}%`; }
function imageUrl(url) { return typeof url === 'string' && /^\/api\/images\/\d+\/(file|processed\/(normalized|mask))$/.test(url) ? url : ''; }

/** HTTP helper: lỗi 4xx/5xx đều hiển thị nội dung cụ thể từ backend. */
async function api(path, options = {}) {
  let response;
  try { response = await fetch(`${API}${path}`, options); }
  catch { throw new Error('Không kết nối được FastAPI. Hãy chạy uvicorn backend.main:app --reload.'); }
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : `Lỗi HTTP ${response.status}`);
  }
  return body;
}

function setStatus(message, kind = '') {
  const element = byId('globalStatus');
  element.className = `status-banner ${kind}`;
  element.textContent = message;
}

function leafDrawing() {
  // SVG chỉ dùng làm biểu tượng, KHÔNG được hiển thị như ảnh thuộc dataset.
  return '<svg viewBox="0 0 120 120" width="120" height="120" aria-hidden="true"><path d="M56 106Q20 80 30 36Q43 9 99 16Q110 80 56 106Z" fill="#5b9a65" stroke="#3c8051" stroke-width="2"/><path d="M56 104Q68 55 98 18M62 84L43 48M72 65L96 63" fill="none" stroke="#c7e6ac" stroke-width="3" stroke-linecap="round"/></svg>';
}

/** Chuyển 6 màn hình, đồng bộ URL # để nút Back/Forward hoạt động. */
function showPage(page) {
  if (!byId(`page-${page}`)) page = 'overview';
  document.querySelectorAll('.screen').forEach((el) => el.classList.toggle('active', el.id === `page-${page}`));
  document.querySelectorAll('.nav-link').forEach((el) => el.classList.toggle('active', el.dataset.page === page));
  const active = $('.nav-link.active');
  byId('crumb').textContent = active?.textContent.trim() ?? 'Tổng quan';
  byId('sidebar').classList.remove('open');
  byId('overlay').classList.remove('open');
  if (location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

/** Các ô dashboard không hard-code số 1.685 nếu chưa nạp database. */
async function loadDashboard() {
  try {
    const data = await api('/dashboard');
    state.ready = Boolean(data.ready);
    const stats = document.querySelectorAll('#page-overview .stat-number');
    [data.total_images, data.categories, 560, data.vector_count].forEach((n, i) => {
      if (stats[i]) stats[i].textContent = formatNumber(n);
    });
    const legends = document.querySelectorAll('#page-overview .legends .legend strong');
    [data.gallery, data.validation, data.test].forEach((n, i) => { if (legends[i]) legends[i].textContent = formatNumber(n); });
    const splitBars = document.querySelectorAll('#page-overview .split-bars i');
    [data.gallery, data.validation, data.test].forEach((n, i) => { if (splitBars[i]) splitBars[i].style.flex = String(Math.max(n, 0.1)); });
    // Đồng bộ các con số trong trang Đánh giá.
    byId('evalGallery').textContent = `${formatNumber(data.gallery)} ảnh`;
    byId('evalValidation').textContent = `${formatNumber(data.validation)} ảnh`;
    byId('evalTest').textContent = `${formatNumber(data.test)} ảnh`;
    byId('testCountChip').textContent = `Tập test: ${formatNumber(data.test)}`;
    const chip = $('.side-bottom .side-chip');
    if (chip) chip.textContent = data.ready ? '● CSDL đã sẵn sàng' : '● CSDL chưa nạp ảnh';
    if (data.ready) {
      setStatus(`Đã nạp ${formatNumber(data.total_images)} ảnh thật · ${data.categories} nhóm · ${formatNumber(data.vector_count)} vector · Pipeline ${data.pipeline_version}.`, 'ready');
    } else {
      setStatus('Chưa nhập bộ dữ liệu. Hãy chạy lệnh python -m backend.tools.import_dataset --source "du_lieu.zip" trong thư mục dự án. Không có kết quả Top 5 cho tới khi nhập thành công.', '');
    }
    // Lấy thống kê đúng theo database, không giả định lúc nào cũng là 77 ảnh cần rà soát.
    const quality = $('#page-overview .callout');
    if (quality) quality.textContent = `Dữ liệu đang vận hành: ${data.dataset_label} · ${data.review_count} ảnh cần rà soát mặt nạ. Kết quả chưa xác nhận tên loài thực vật.`;
    return data;
  } catch (error) {
    setStatus(error.message, 'error');
    state.ready = false;
  }
}

/** Danh mục mỗi nhóm và một ảnh PNG đại diện THẬT (không lấy SVG để giả ảnh). */
async function loadGroups() {
  const root = byId('libraryGrid');
  try {
    state.groups = (await api('/categories')).items;
    renderGroups();
  } catch (error) { root.innerHTML = `<p class="empty-hint">${safe(error.message)}</p>`; }
}
function renderGroups() {
  const term = byId('groupFilter').value.trim().toLowerCase().replace('nhóm', '').trim();
  const sort = byId('sortGroups').value;
  const groups = state.groups.filter((g) => !term || g.group_id.includes(term));
  groups.sort((a, b) => sort === 'count' ? b.image_count - a.image_count :
    sort === 'few' ? a.image_count - b.image_count :
    sort === 'desc' ? Number(b.group_id) - Number(a.group_id) : Number(a.group_id) - Number(b.group_id));
  byId('groupCount').textContent = `${groups.length} / ${state.groups.length} nhóm`;
  byId('libraryGrid').innerHTML = groups.length ? groups.map((g) => `
    <button type="button" class="group-tile" data-group="${safe(g.group_id)}">
      <div class="group-image">${g.thumbnail_url ? `<img loading="lazy" src="${imageUrl(g.thumbnail_url)}" alt="Ảnh thật nhóm ${safe(g.group_id)}">` : '<span class="muted">Chưa có ảnh</span>'}</div>
      <div class="group-name"><strong>Nhóm ${safe(g.group_id)}</strong><span class="count">${formatNumber(g.image_count)} ảnh</span></div>
      <div class="tile-bottom">Nhấp để duyệt ảnh thực tế</div>
    </button>`).join('') : '<div class="empty-hint">Không tìm thấy mã nhóm.</div>';
  document.querySelectorAll('.group-tile[data-group]').forEach((btn) => {
    btn.addEventListener('click', () => { state.activeGroup = btn.dataset.group; state.page = 1; loadGroupImages(); });
  });
}

/** Phân trang ảnh theo nhóm, hiển thị metadata và mask từ API. */
async function loadGroupImages() {
  const holder = byId('libraryResults');
  holder.innerHTML = '<div class="card">Đang tải danh sách ảnh...</div>';
  try {
    const params = new URLSearchParams({ group_id: state.activeGroup, page: String(state.page), page_size: '16' });
    const data = await api(`/images?${params}`);
    const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    holder.innerHTML = `<div class="card"><div class="card-heading"><h2>Ảnh thật · Nhóm ${safe(state.activeGroup)}</h2><span class="pill">${formatNumber(data.total)} ảnh</span></div>
      <div class="image-results-grid">${data.items.map((im) => `<button type="button" class="image-item" data-image-id="${im.image_id}">
        <img loading="lazy" src="${imageUrl(im.image_url)}" alt="Lá ${safe(im.file_name)}">
        <div><b>${safe(im.file_name)}</b><small>${safe(im.split)} · Mask: ${im.quality_status === 'review' ? 'Cần xem lại' : 'OK'}</small></div></button>`).join('')}</div>
      <div class="pagination"><button class="btn outline" data-dir="-1" ${state.page === 1 ? 'disabled' : ''}>← Trước</button><span>Trang ${state.page}/${totalPages}</span><button class="btn outline" data-dir="1" ${state.page === totalPages ? 'disabled' : ''}>Sau →</button></div></div>`;
    holder.querySelectorAll('[data-image-id]').forEach((x) => x.addEventListener('click', () => showImageDetail(Number(x.dataset.imageId))));
    holder.querySelectorAll('[data-dir]').forEach((x) => x.addEventListener('click', () => {
      state.page += Number(x.dataset.dir); loadGroupImages();
    }));
    holder.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (error) { holder.innerHTML = `<div class="status-banner error">${safe(error.message)}</div>`; }
}

/** Chọn/tải ảnh lên; browser chỉ preview, không gọi thuật toán ở client. */
function chooseFile(file) {
  const error = byId('fileError'); error.style.display = 'none';
  if (!file) return;
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    error.textContent = 'Định dạng không hợp lệ: hãy chọn PNG, JPG hoặc WEBP.';
    error.style.display = 'block'; return;
  }
  if (file.size > 10 * 1024 * 1024) {
    error.textContent = 'Tệp vượt 10 MB.'; error.style.display = 'block'; return;
  }
  state.selectedFile = file;
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = URL.createObjectURL(file);
  const preview = byId('filePreview');
  preview.src = state.previewUrl;
  preview.onload = () => {
    preview.style.display = 'block'; byId('uploadIcon').style.display = 'none';
    byId('dropTitle').textContent = file.name;
    byId('dropText').textContent = `${formatNumber(Math.round(file.size / 1024))} KB · ${preview.naturalWidth}×${preview.naturalHeight} px`;
    byId('fileStatus').textContent = 'Ảnh đã chọn; bấm Tìm kiếm để chạy thuật toán thật.';
    byId('selectTrigger').textContent = 'Đổi ảnh';
  };
  preview.onerror = () => { state.selectedFile = null; error.textContent = 'Ảnh bị lỗi hoặc không giải mã được.'; error.style.display = 'block'; };
}

function readWeights() {
  const raw = Object.fromEntries(GROUPS.map((key) => [key, Number(byId(`weight-${key}`).value)]));
  const sum = Object.values(raw).reduce((a, b) => a + b, 0);
  GROUPS.forEach((key) => { byId(`v-${key}`).textContent = `${sum ? 100 * raw[key] / sum : 0}%`.replace(/(\.\d\d)\d+/, '$1'); });
  byId('weightsNote').textContent = sum ? `Tổng trọng số nhập: ${sum}. Backend chuẩn hóa về tổng 1.` : 'Cần ít nhất một trọng số lớn hơn 0.';
  return raw;
}

/** Backend trả 5 ảnh gallery sắp theo distance_total tăng. */
async function doSearch() {
  const error = byId('fileError'); error.style.display = 'none';
  if (!state.selectedFile) { error.textContent = 'Bạn chưa chọn ảnh truy vấn.'; error.style.display = 'block'; return; }
  if (!state.ready) { error.textContent = 'CSDL chưa sẵn sàng: hãy nhập ZIP ảnh trước.'; error.style.display = 'block'; return; }
  const button = byId('searchBtn');
  button.disabled = true; button.textContent = 'Đang trích xuất 560 đặc trưng và tìm Top 5...';
  const body = new FormData(); body.append('file', state.selectedFile);
  Object.entries(readWeights()).forEach(([key, value]) => body.append(key, String(value)));
  try {
    const result = await api('/search', { method: 'POST', body });
    byId('emptyResults').style.display = 'none';
    const grid = byId('resultGrid'); grid.style.display = 'grid';
    grid.innerHTML = result.results.map((item) => `
      <div class="result-card"><button data-image-id="${item.image_id}" type="button" title="Xem chi tiết ảnh">
        <div class="result-image"><span class="rank">#${item.rank}</span><img src="${imageUrl(item.image_url)}" alt="${safe(item.file_name)}"></div>
        <div class="result-info"><b>${safe(item.file_name)}</b><p>Nhóm hình thái ${safe(item.group_id)}</p>
        <span class="demo-stamp" style="background:#eaf5e8;color:#346e4c">D = ${Number(item.distance_total).toFixed(5)}</span>
        <p>Màu ${item.distance_by_group.color.toFixed(3)} · Hình ${item.distance_by_group.shape.toFixed(3)}</p>
        <p>Gờ ${item.distance_by_group.ridge.toFixed(3)} · Kết cấu ${item.distance_by_group.texture.toFixed(3)}</p></div>
      </button></div>`).join('');
    grid.querySelectorAll('[data-image-id]').forEach((x) => x.addEventListener('click', () => showImageDetail(Number(x.dataset.imageId))));
    byId('demoNotice').style.display = 'block';
    byId('demoNotice').innerHTML = `<strong>Kết quả tính thật:</strong> so sánh với ${formatNumber(result.gallery_count)} ảnh gallery trong ${result.runtime_ms} ms. D là khoảng cách, không phải phần trăm xác suất đúng loài.${result.query.quality_warning ? `<br>${safe(result.query.quality_warning)}` : ''}<div class="img-query-preview"><figure><img alt="Ảnh sau chuẩn hóa" src="${result.query.normalized_image}"><figcaption>Ảnh chuẩn hóa</figcaption></figure><figure><img alt="Mặt nạ" src="${result.query.mask_image}"><figcaption>Mask nhị phân</figcaption></figure></div>`;
    byId('resultsContainer').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    error.textContent = e.message; error.style.display = 'block';
  } finally { button.disabled = false; button.textContent = '⌕  Tìm kiếm Top 5'; }
}

/** Mở chi tiết một ảnh: ảnh gốc, ảnh chuẩn hóa, mask, metadata và vector mẫu. */
async function showImageDetail(imageId) {
  const modal = byId('detailModal'); const content = byId('detailContent');
  modal.classList.add('open'); content.textContent = 'Đang tải thông tin ảnh…';
  try {
    const data = await api(`/images/${imageId}`);
    const features = Object.entries(data.features).map(([group, value]) =>
      `<div><strong>${safe(group)} (${value.dimension} chiều)</strong><div class="muted">${value.sample_values.map((v) => Number(v).toFixed(4)).join(', ')}…</div></div>`).join('');
    content.innerHTML = `<div class="modal-header"><h2 style="margin:0">${safe(data.file_name)} · Nhóm ${safe(data.group_id)}</h2><button class="btn outline" id="closeDetail">Đóng ×</button></div>
      <p class="small muted">Ảnh thật được nhập từ ZIP, qua cùng pipeline xử lý cho toàn bộ tập dữ liệu.</p>
      <div class="modal-images"><figure><img src="${imageUrl(data.image_url)}" alt="Ảnh gốc"><figcaption>Ảnh gốc</figcaption></figure>
      <figure><img src="${imageUrl(data.normalized_url)}" alt="Ảnh chuẩn hóa"><figcaption>Chuẩn hóa 512×512</figcaption></figure>
      <figure><img src="${imageUrl(data.mask_url)}" alt="Mặt nạ lá"><figcaption>Mask phân đoạn</figcaption></figure></div>
      <div class="detail-grid"><div><b>Tập phân chia:</b> ${safe(data.split)}</div><div><b>Trạng thái:</b> ${safe(data.quality_status)}</div>
      <div><b>Mask ratio:</b> ${(Number(data.mask_ratio)*100).toFixed(3)}%</div><div><b>SHA-256:</b> ${safe(data.sha256.slice(0,24))}…</div>${features}</div>`;
    byId('closeDetail').addEventListener('click', closeDetail);
  } catch (error) { content.textContent = `Lỗi: ${error.message}`; }
}
function closeDetail() { byId('detailModal').classList.remove('open'); }

/** Các chỉ số thực nghiệm chỉ cập nhật từ phản hồi API, không ước lượng. */
function updateEvaluation(data) {
  const m = data.metrics;
  byId('metricAccuracy').textContent = percent(m.accuracy_at_1);
  byId('metricPrecision').textContent = percent(m.precision_at_5);
  byId('metricMrr').textContent = percent(m.mrr_at_5);
  [byId('metricAccuracy'), byId('metricPrecision'), byId('metricMrr')].forEach((x) => x.className = 'metrics-live');
  byId('evaluationStatusValue').textContent = `Đã đánh giá #${data.evaluation_id}`;
  byId('evaluationMessage').textContent = `Kết quả thực nghiệm #${data.evaluation_id} · Tập ${data.split} · ${m.queries} truy vấn · Gallery ${m.gallery_count} ảnh · ${m.runtime_ms} ms. Mã nhóm chưa xác nhận là tên loài.`;
}
async function loadLatestEvaluation() {
  try { updateEvaluation(await api('/evaluations/latest')); }
  catch { byId('evaluationMessage').textContent = 'Chưa có lần chạy đánh giá nào trong CSDL.'; }
}
async function runEvaluation(split) {
  const button = split === 'test' ? byId('runEvaluation') : byId('runValidation');
  button.disabled = true; const previous = button.textContent; button.textContent = 'Đang tính toán…';
  byId('evaluationMessage').textContent = `Đang đánh giá trên tập ${split}; chỉ so sánh với gallery.`;
  try {
    const weights = Object.fromEntries(Object.entries(readWeights()).map(([key, value]) => [key, value / 100]));
    const result = await api('/evaluate', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ split, weights }) });
    updateEvaluation(result);
    if (result.examples_wrong?.length) {
      const preview = result.examples_wrong.slice(0, 3).map((x) => `${safe(x.file_name)} (nhóm ${safe(x.group_id)}): kết quả #1 là nhóm ${safe(x.top5[0].group_id)}`).join(' · ');
      byId('evaluationMessage').textContent += ` Ví dụ sai Top 1: ${preview}`;
    }
  } catch (error) { byId('evaluationMessage').textContent = `Không đánh giá được: ${error.message}`; }
  finally { button.disabled = false; button.textContent = previous; }
}

/** Dữ liệu chất lượng cũng đọc từ backend, không dùng số cố định trong HTML. */
async function loadQuality() {
  const stats = byId('qualityStats');
  const gallery = byId('qualityReviewGallery');
  const csvLink = byId('qualityCsv');
  try {
    const info = await api('/quality');
    let summary = `${formatNumber(info.review_count)} ảnh được đánh dấu cần xem lại mặt nạ.`;
    if (info.audit_available) {
      summary += ` Công cụ pHash ghi nhận ${formatNumber(info.candidate_pairs)} cặp nghi gần trùng, ` +
        `${formatNumber(info.cross_split_pairs)} cặp khác tập (trong đó ` +
        `${formatNumber(info.same_group_cross_split)} cặp cùng mã nhóm).`;
      csvLink.style.display = 'inline-flex';
    } else {
      summary += ' Chưa có báo cáo pHash; hãy chạy công cụ audit trong backend.';
      csvLink.style.display = 'none';
    }
    stats.textContent = summary;
    gallery.innerHTML = info.review_samples.length ? info.review_samples.map((image) => `
      <button type="button" class="image-item" data-review-id="${image.image_id}">
        <img loading="lazy" src="${imageUrl(image.image_url)}" alt="Mẫu lá ${safe(image.file_name)}">
        <div><b>${safe(image.file_name)}</b><small>Nhóm ${safe(image.group_id)} · ${safe(image.split)} · ` +
        `Mask ${(Number(image.mask_ratio)*100).toFixed(2)}%</small></div>
      </button>`).join('') : '<div class="empty-hint">Không có ảnh cần rà soát.</div>';
    gallery.querySelectorAll('[data-review-id]').forEach((button) =>
      button.addEventListener('click', () => showImageDetail(Number(button.dataset.reviewId))));
  } catch (e) { stats.textContent = `Không đọc được thống kê chất lượng: ${e.message}`; }
}

function bindEvents() {
  document.querySelectorAll('[data-page]').forEach((el) => el.addEventListener('click', () => showPage(el.dataset.page)));
  document.querySelectorAll('[data-goto]').forEach((el) => el.addEventListener('click', () => showPage(el.dataset.goto)));
  window.addEventListener('hashchange', () => showPage(location.hash.slice(1)));
  byId('menuBtn').addEventListener('click', () => { byId('sidebar').classList.toggle('open'); byId('overlay').classList.toggle('open'); });
  byId('overlay').addEventListener('click', () => { byId('sidebar').classList.remove('open'); byId('overlay').classList.remove('open'); });
  byId('groupFilter').addEventListener('input', renderGroups);
  byId('sortGroups').addEventListener('change', renderGroups);
  const input = byId('fileInput'), drop = byId('dropZone');
  drop.addEventListener('click', (e) => { if (e.target !== input) input.click(); });
  drop.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  input.addEventListener('change', () => chooseFile(input.files[0]));
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('drag'); });
  drop.addEventListener('dragleave', () => drop.classList.remove('drag'));
  drop.addEventListener('drop', (e) => { e.preventDefault(); drop.classList.remove('drag'); chooseFile(e.dataTransfer.files[0]); });
  GROUPS.forEach((key) => byId(`weight-${key}`).addEventListener('input', readWeights));
  byId('resetWeights').addEventListener('click', () => {
    Object.entries(DEFAULT_WEIGHTS).forEach(([key, value]) => byId(`weight-${key}`).value = value);
    readWeights();
  });
  byId('searchBtn').addEventListener('click', doSearch);
  byId('runEvaluation').addEventListener('click', () => runEvaluation('test'));
  byId('runValidation').addEventListener('click', () => runEvaluation('validation'));
  byId('detailModal').addEventListener('click', (e) => { if (e.target === byId('detailModal')) closeDetail(); });
  window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetail(); });
}

// Khởi động; dữ liệu lúc chưa nhập sẽ trả 0 thay vì 1.685 mặc định.
byId('heroLeaf').innerHTML = leafDrawing();
bindEvents();
readWeights();
showPage(location.hash.slice(1) || 'overview');
Promise.all([loadDashboard(), loadGroups(), loadLatestEvaluation(), loadQuality()]);

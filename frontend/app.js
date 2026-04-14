
const API_BASE = "http://127.0.0.1:8000";

const el = {
  navUpload: document.getElementById("navUpload"),
  navOverview: document.getElementById("navOverview"),
  pageUpload: document.getElementById("pageUpload"),
  pageOverview: document.getElementById("pageOverview"),
  reloadBtn: document.getElementById("reloadBtn"),
  runPipelineBtn: document.getElementById("runPipelineBtn"),
  uploadBtn: document.getElementById("uploadBtn"),
  clearHtmlBtn: document.getElementById("clearHtmlBtn"),
  clearDataBtn: document.getElementById("clearDataBtn"),
  htmlFilesInput: document.getElementById("htmlFilesInput"),
  htmlDirInput: document.getElementById("htmlDirInput"),
  selectedHtmlInfo: document.getElementById("selectedHtmlInfo"),
  uploadLoading: document.getElementById("uploadLoading"),
  uploadLoadingText: document.getElementById("uploadLoadingText"),
  statusText: document.getElementById("statusText"),
  totalNotes: document.getElementById("totalNotes"),
  avgSentiment: document.getElementById("avgSentiment"),
  vlmCount: document.getElementById("vlmCount"),
  recommendCount: document.getElementById("recommendCount"),
  sentimentPie: document.getElementById("sentimentPie"),
  interestBars: document.getElementById("interestBars"),
  routeList: document.getElementById("routeList"),
  cultureList: document.getElementById("cultureList"),
  singleInterestList: document.getElementById("singleInterestList"),
  singleSentimentList: document.getElementById("singleSentimentList"),
  uploadVlmAnswers: document.getElementById("uploadVlmAnswers"),
};

let uploadWaitTimerId = null;
let uploadWaitSeconds = 0;

function setStatus(text) {
  el.statusText.textContent = text;
}

function startUploadWaiting() {
  uploadWaitSeconds = 0;
  el.uploadBtn.disabled = true;
  el.uploadLoading.classList.remove("hidden");
  el.uploadLoadingText.textContent = "分析中... 已等待 0s";
  if (uploadWaitTimerId) {
    clearInterval(uploadWaitTimerId);
  }
  uploadWaitTimerId = setInterval(() => {
    uploadWaitSeconds += 1;
    el.uploadLoadingText.textContent = `分析中... 已等待 ${uploadWaitSeconds}s`;
  }, 1000);
}

function stopUploadWaiting() {
  el.uploadBtn.disabled = false;
  el.uploadLoading.classList.add("hidden");
  if (uploadWaitTimerId) {
    clearInterval(uploadWaitTimerId);
    uploadWaitTimerId = null;
  }
}

function collectSelectedHtmlFiles() {
  const fromFiles = Array.from(el.htmlFilesInput.files || []);
  const fromDir = Array.from(el.htmlDirInput.files || []);
  const isHtml = (file) => {
    const name = String(file?.name || "").toLowerCase();
    return name.endsWith(".html") || name.endsWith(".htm");
  };
  return [...fromFiles, ...fromDir].filter(isHtml);
}

function refreshSelectedHtmlInfo() {
  const htmlFiles = collectSelectedHtmlFiles();
  el.selectedHtmlInfo.textContent = `当前已选 HTML：${htmlFiles.length}`;
}

function switchPage(page) {
  const isUpload = page === "upload";
  el.navUpload.classList.toggle("active", isUpload);
  el.navOverview.classList.toggle("active", !isUpload);
  el.pageUpload.classList.toggle("active", isUpload);
  el.pageOverview.classList.toggle("active", !isUpload);
}

// 图像兴趣标签中文映射
const LABEL_ZH_MAP = {
  "courtyard_garden": "庭院园林",
  "garden_plants": "园林植物",
  "architecture_overview": "建筑全景",
  "architectural_detail": "建筑细节",
  "plaque_inscription": "匾额题刻",
  "interior_space": "室内空间",
  "cultural_relic": "文物陈设",
  "visitor_crowd": "游客人流",
  "landscape_view": "景观视野",
  "decorative_art": "装饰艺术",
  "historical_photo": "历史照片",
  "night_view": "夜景灯光"
};

function barRow(label, value, maxValue) {
  const ratio = maxValue > 0 ? Math.max(0.04, value / maxValue) : 0;
  const labelZh = LABEL_ZH_MAP[label] || label;
  return `
    <div class="bar-row">
      <div class="bar-label" title="${label}">${labelZh}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${ratio * 100}%"></div></div>
      <div>${value}</div>
    </div>
  `;
}

function renderBars(container, rows) {
  if (!rows.length) {
    container.innerHTML = "<p>No data</p>";
    return;
  }
  const maxValue = Math.max(...rows.map((x) => x.value));
  container.innerHTML = rows.map((x) => barRow(x.label, x.value, maxValue)).join("");
}

function renderList(container, rows, formatter, emptyText = "No data") {
  if (!rows.length) {
    container.innerHTML = `<li>${emptyText}</li>`;
    return;
  }
  container.innerHTML = rows.map((item) => `<li>${formatter(item)}</li>`).join("");
}

function renderVlmAnswers(rows) {
  if (!rows.length) {
    el.uploadVlmAnswers.innerHTML = `
      <article class="chat-item fill">
        <p class="chat-meta">等待上传</p>
        <div class="dialog-row user">
          <div class="bubble user">
            <p>请识别这张游客图片的兴趣点，并给出理由。</p>
          </div>
          <div class="avatar user">U</div>
        </div>
        <div class="dialog-row assistant">
          <div class="avatar assistant">AI</div>
          <div class="bubble assistant">
            <p>已进入大模型对话模式。请先上传 HTML 文件，我会在这里逐条展示识别回答。</p>
          </div>
        </div>
      </article>
    `;
    return;
  }
  const turns = rows
    .map((row, idx) => {
      const raw = JSON.stringify(row.raw_model_result ?? {}, null, 2);
      return `
        <p class="chat-meta turn-meta">#${idx + 1} | note=${row.note_id ?? ""} | image=${row.image_name ?? ""}</p>
        <div class="dialog-row user">
          <div class="bubble user">
            <p>请识别这张游客图片的兴趣点，并给出理由。</p>
          </div>
          <div class="avatar user">U</div>
        </div>
        <div class="dialog-row assistant">
          <div class="avatar assistant">AI</div>
          <div class="bubble assistant">
            <p><strong>Top标签：</strong>${row.predicted_top_label ?? ""} (${row.predicted_top_label_zh ?? ""})</p>
            <p><strong>候选标签：</strong>${(row.predicted_labels_zh || []).join(" / ") || "-"}</p>
            <p><strong>置信度：</strong>${row.confidence ?? 0}</p>
            <p><strong>回答理由：</strong>${row.reason || "-"}</p>
            <details>
              <summary>查看原始返回 JSON</summary>
              <pre>${raw}</pre>
            </details>
          </div>
        </div>
      `;
    })
    .join("");

  el.uploadVlmAnswers.innerHTML = `
    <article class="chat-item stream-session">
      ${turns}
    </article>
  `;
}

function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function pieSlicePath(cx, cy, r, startAngle, endAngle) {
  const angle = endAngle - startAngle;
  // 处理 360 度完整圆形的情况
  if (angle >= 360) {
    return `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
  }
  // 处理接近 360 度的情况，避免渲染问题
  if (angle > 359.9) {
    return `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
  }
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = angle <= 180 ? 0 : 1;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y} Z`;
}

function renderPieChart(container, rows, colors) {
  const validRows = rows.filter((item) => Number(item.value) > 0);
  if (!validRows.length) {
    container.innerHTML = "<p>No data</p>";
    return;
  }
  const total = validRows.reduce((acc, item) => acc + Number(item.value), 0);
  const radius = 110;
  const cx = 120;
  const cy = 120;
  let currentAngle = 0;
  const slices = validRows
    .map((item, idx) => {
      const value = Number(item.value);
      const angle = (value / total) * 360;
      const d = pieSlicePath(cx, cy, radius, currentAngle, currentAngle + angle);
      const color = colors[idx % colors.length];
      currentAngle += angle;
      return `<path d="${d}" fill="${color}"></path>`;
    })
    .join("");

  const legend = validRows
    .map((item, idx) => {
      const color = colors[idx % colors.length];
      const percent = ((Number(item.value) / total) * 100).toFixed(1);
      return `<li><span class="swatch" style="background:${color}"></span>${item.label}: ${item.value} (${percent}%)</li>`;
    })
    .join("");

  container.innerHTML = `
    <div class="pie-chart">
      <svg class="pie-svg" viewBox="0 0 240 240" role="img" aria-label="pie chart">
        ${slices}
      </svg>
      <ul class="pie-legend">${legend}</ul>
    </div>
  `;
}
function renderDashboard(data) {
  const sentiment = data.sentiment_summary || {};
  // 支持多种字段名：sentiment_distribution / distribution, sentiment_distribution_zh / distribution_zh
  const distribution = sentiment.sentiment_distribution || sentiment.distribution || {};
  const distributionZh = sentiment.sentiment_distribution_zh || sentiment.distribution_zh || {};
  const management = data.management || {};
  const routeRecommendations = management.route_recommendations || [];
  const cultureRecommendations = management.culture_recommendations || [];
  const topLabels = (management.visual_interest && management.visual_interest.top_labels) || [];

  el.totalNotes.textContent = String(sentiment.total_notes ?? management.data_quality?.sentiment_note_count ?? 0);
  // 支持两种字段名：average_sentiment_score (来自直接summary) 或 average_score (来自summarize_sentiment)
  el.avgSentiment.textContent = String(sentiment.average_sentiment_score ?? sentiment.average_score ?? 0);
  el.vlmCount.textContent = String(data.vlm_prediction_count ?? 0);
  el.recommendCount.textContent = String(routeRecommendations.length + cultureRecommendations.length);

  // 使用中文标签如果可用，否则使用英文
  const hasZhData = Object.keys(distributionZh).length > 0;
  const distToUse = hasZhData ? distributionZh : distribution;
  const labelMap = hasZhData 
    ? { "正向": "positive", "中性": "neutral", "负向": "negative" }
    : { "positive": "positive", "neutral": "neutral", "negative": "negative" };

  renderPieChart(
    el.sentimentPie,
    [
      { label: hasZhData ? "正向" : "positive", value: distToUse["正向"] || distToUse["positive"] || 0 },
      { label: hasZhData ? "中性" : "neutral", value: distToUse["中性"] || distToUse["neutral"] || 0 },
      { label: hasZhData ? "负向" : "negative", value: distToUse["负向"] || distToUse["negative"] || 0 },
    ],
    ["#22c55e", "#64748b", "#ef4444"]
  );
  renderBars(
    el.interestBars,
    topLabels.map((item) => ({ label: item.label, value: item.count }))
  );
  // 优先级颜色映射
  const priorityColorClass = (priority) => {
    const p = String(priority).toLowerCase();
    if (p === "紧急" || p === "emergency") return "priority-emergency";
    if (p === "高" || p === "high") return "priority-high";
    if (p === "中" || p === "medium") return "priority-medium";
    if (p === "低" || p === "low") return "priority-low";
    return "priority-medium";
  };

  renderList(el.routeList, routeRecommendations, (item) => {
    const colorClass = priorityColorClass(item.priority);
    return `<span class="priority-tag ${colorClass}">${item.priority}</span> ${item.theme}: ${item.action}`;
  });
  renderList(el.cultureList, cultureRecommendations, (item) => {
    const labelZh = LABEL_ZH_MAP[item.focus_label] || item.focus_label;
    const colorClass = priorityColorClass(item.priority);
    return `<span class="priority-tag ${colorClass}">${item.priority}</span> ${labelZh}: ${item.action}`;
  });
}

function renderSingleUpload(payload) {
  const scoped = payload.single_upload_recommendations || {};
  const visualInterest = scoped.visual_interest || {};
  const sentimentSummary = scoped.sentiment_summary || {};
  const answers = payload.single_upload_vlm_answers || [];
  const topLabels = visualInterest.top_labels || [];
  const distribution = sentimentSummary.distribution || {};
  const avgScore = sentimentSummary.average_score ?? 0;
  const negSignals = sentimentSummary.top_negative_signals || [];

  renderList(
    el.singleInterestList,
    topLabels,
    (item) => {
      const labelZh = LABEL_ZH_MAP[item.label] || item.label;
      return `标签：${labelZh}\n出现次数：${item.count}`;
    },
    "暂无图像兴趣数据。"
  );
  renderList(
    el.singleSentimentList,
    [
      `情感分布：positive=${distribution.positive || 0}, neutral=${distribution.neutral || 0}, negative=${distribution.negative || 0}`,
      `平均情感分：${avgScore}`,
      `负向信号：${negSignals.length ? negSignals.map((x) => `${x.issue}(${x.count})`).join("；") : "暂无明显负向信号"}`,
    ],
    (item) => item,
    "暂无情感分布数据。"
  );
  renderVlmAnswers(answers);
}

async function fetchDashboard() {
  const res = await fetch(`${API_BASE}/api/dashboard`);
  if (!res.ok) throw new Error(`dashboard api failed: ${res.status}`);
  return res.json();
}

async function reloadData(recompute = false) {
  try {
    setStatus(recompute ? "Recomputing reports..." : "Loading dashboard...");
    if (recompute) {
      const res = await fetch(`${API_BASE}/api/recompute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_sentiment: true, run_management: true }),
      });
      if (!res.ok) throw new Error(`recompute failed: ${res.status}`);
    }
    const dashboard = await fetchDashboard();
    renderDashboard(dashboard);
    setStatus(`Updated at ${new Date().toLocaleTimeString()}`);
  } catch (err) {
    console.error(err);
    setStatus(`Load failed: ${err.message}`);
  }
}
async function runPipeline() {
  try {
    setStatus("Running full pipeline...");
    const res = await fetch(`${API_BASE}/api/run-pipeline`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ download_images: true, pause_seconds: 0, limit: 0 }),
    });
    if (!res.ok) throw new Error(`run pipeline failed: ${res.status}`);
    const payload = await res.json();
    renderDashboard(payload.dashboard || {});
    const vlm = payload.vlm || {};
    setStatus(vlm.ran ? `Pipeline done. VLM predictions: ${vlm.predictions_saved}` : `Pipeline done. VLM skipped: ${vlm.reason || "unknown"}`);
  } catch (err) {
    console.error(err);
    setStatus(`Pipeline failed: ${err.message}`);
  }
}

async function uploadHtmlAndAnalyze() {
  const files = collectSelectedHtmlFiles();
  if (!files.length) {
    setStatus("请选择至少一个 HTML 文件或文件夹。");
    return;
  }

  startUploadWaiting();
  try {
    setStatus(`Uploading ${files.length} HTML files and running VLM analysis...`);
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    const res = await fetch(`${API_BASE}/api/upload-html`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`upload failed: ${res.status} ${await res.text()}`);

    const payload = await res.json();
    renderDashboard(payload.dashboard || {});
    renderSingleUpload(payload);
    switchPage("upload");

    const importedNotes = payload.pipeline?.imported_notes ?? 0;
    const vlmRan = payload.pipeline?.vlm?.ran;
    setStatus(`Upload done. Files: ${files.length}, Imported notes: ${importedNotes}, VLM: ${vlmRan ? "on" : "off"}`);
  } catch (err) {
    console.error(err);
    setStatus(`Upload failed: ${err.message}`);
  } finally {
    stopUploadWaiting();
  }
}

async function clearRecordedHtmlFiles() {
  const confirmed = window.confirm("确定要清空当前已记录的 HTML 文件吗？此操作不可恢复。");
  if (!confirmed) {
    return;
  }
  try {
    setStatus("Clearing recorded HTML files...");
    const res = await fetch(`${API_BASE}/api/clear-html-files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`clear html failed: ${res.status}`);
    const payload = await res.json();
    renderDashboard(payload.dashboard || {});
    el.htmlFilesInput.value = "";
    el.htmlDirInput.value = "";
    refreshSelectedHtmlInfo();
    renderVlmAnswers([]);
    el.singleInterestList.innerHTML = "<li>暂无图像兴趣数据。</li>";
    el.singleSentimentList.innerHTML = "<li>暂无情感分布数据。</li>";
    setStatus(`HTML cleared. Deleted files: ${payload.deleted_count ?? 0}`);
  } catch (err) {
    console.error(err);
    setStatus(`Clear failed: ${err.message}`);
  }
}

async function clearAllDataFiles() {
  const confirmed = window.confirm(
    "确定要清空 data 目录下的 raw/interim/processed 全部内容吗？此操作不可恢复。"
  );
  if (!confirmed) {
    return;
  }
  try {
    setStatus("Clearing all data files...");
    const res = await fetch(`${API_BASE}/api/clear-data-files`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error(`clear data failed: ${res.status}`);
    const payload = await res.json();
    renderDashboard(payload.dashboard || {});
    el.htmlFilesInput.value = "";
    el.htmlDirInput.value = "";
    refreshSelectedHtmlInfo();
    renderVlmAnswers([]);
    el.singleInterestList.innerHTML = "<li>暂无图像兴趣数据。</li>";
    el.singleSentimentList.innerHTML = "<li>暂无情感分布数据。</li>";
    setStatus(
      `Data cleared. Deleted files: ${payload.deleted_file_count ?? 0}, dirs: ${payload.deleted_dir_count ?? 0}`
    );
  } catch (err) {
    console.error(err);
    setStatus(`Clear data failed: ${err.message}`);
  }
}

el.navUpload.addEventListener("click", () => switchPage("upload"));
el.navOverview.addEventListener("click", () => switchPage("overview"));
el.reloadBtn.addEventListener("click", () => reloadData(true));
el.runPipelineBtn.addEventListener("click", runPipeline);
el.uploadBtn.addEventListener("click", uploadHtmlAndAnalyze);
el.clearHtmlBtn.addEventListener("click", clearRecordedHtmlFiles);
el.clearDataBtn.addEventListener("click", clearAllDataFiles);
el.htmlFilesInput.addEventListener("change", refreshSelectedHtmlInfo);
el.htmlDirInput.addEventListener("change", refreshSelectedHtmlInfo);

switchPage("upload");
renderVlmAnswers([]);
el.singleInterestList.innerHTML = "<li>暂无图像兴趣数据。</li>";
el.singleSentimentList.innerHTML = "<li>暂无情感分布数据。</li>";
refreshSelectedHtmlInfo();
reloadData(false);

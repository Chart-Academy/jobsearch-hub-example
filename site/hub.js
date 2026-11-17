// My Job Search Hub — the page's JavaScript.
// It asks hub.py for your data (/api/hub), draws the page, and saves your
// checks and tracker back through hub.py. Every value is escaped before it
// goes on the page.

"use strict";

const COLUMNS = ["Company", "Role", "Link", "QUICK HIRE", "Date applied", "Status",
  "Follow-up date", "Interview date", "Offer date", "Notes"];
const DATE_COLUMNS = ["Date applied", "Follow-up date", "Interview date", "Offer date"];
const STATUSES = ["Interested", "Applied", "Interview", "Offer", "Not selected", "Withdrew"];

let hub = { profile: null, top10: [], jobs: [], tracker: [], documents: [], interviews: [] };
let trackerChanged = false;

// ---------- small helpers ----------

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function safeLink(link) {
  try {
    const url = new URL(link);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : "";
  } catch (err) {
    return "";
  }
}

function list(items) {
  if (!items || !items.length) return '<p class="muted">None yet.</p>';
  return "<ul>" + items.map((item) => "<li>" + esc(item) + "</li>").join("") + "</ul>";
}

let messageTimer = null;
function say(text, isError) {
  const box = document.getElementById("message");
  box.textContent = text;
  box.className = "show" + (isError ? " error" : "");
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => { box.className = ""; }, isError ? 7000 : 3500);
}

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  let response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    throw new Error("Can't reach your hub. Is python hub.py still running in your other terminal window?");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Something went wrong. Please try again.");
  return data;
}

function jobById(id) {
  return hub.jobs.find((job) => job.id === id);
}

// ---------- 1 & 2. header line and progress ----------

function drawHeader() {
  const roles = hub.profile && hub.profile.target_roles;
  document.getElementById("searching-for").textContent = roles && roles.length
    ? "Searching for: " + roles.join(" · ")
    : "Run python agents/build_profile.py to set up your search.";
}

function averageStar() {
  const scores = [];
  hub.interviews.forEach((session) => {
    (session.answers || []).forEach((answer) => {
      const score = answer.feedback ? answer.feedback.score : answer.score;
      if (typeof score === "number") scores.push(score);
    });
  });
  if (!scores.length) return "–";
  return (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) + "/5";
}

function drawProgress() {
  const topJobs = hub.top10.map(jobById).filter(Boolean);
  const checked = topJobs.filter((job) => job.student_check && job.student_check.checked).length;
  const sent = hub.tracker.filter((row) => row.Status && row.Status !== "Interested").length;
  const stats = [
    [hub.jobs.length, "openings found", "#jump"],
    [checked + "/" + topJobs.length, "top jobs I've checked"],
    [hub.tracker.length, "jobs in my tracker"],
    [sent, "applications sent"],
    [hub.interviews.length, "practice interviews"],
    [averageStar(), "my average STAR score"],
  ];
  document.getElementById("progress").innerHTML = stats.map(([number, label, link]) => {
    const inside = '<div class="number">' + esc(number) + '</div><div class="label">' + esc(label) + "</div>";
    return '<div class="stat">' + (link ? '<a href="' + link + '">' + inside + "</a>" : inside) + "</div>";
  }).join("");
  drawMeters();
}

// ---------- tracker thermometers: where my applications are ----------

// Each thermometer shows what share of my tracked jobs are at that stage right now.
const STAGES = [
  { name: "Interested", statuses: ["Interested"], color: "#7a7a7a" },
  { name: "Applied", statuses: ["Applied"], color: "var(--flag-green)" },
  { name: "Interviewing", statuses: ["Interview"], color: "var(--flag-black)" },
  { name: "Offers", statuses: ["Offer"], color: "var(--quick)" },
  { name: "Closed", statuses: ["Not selected", "Withdrew"], color: "var(--flag-red)" },
];

function drawMeters() {
  const total = hub.tracker.length;
  document.getElementById("meter-title").textContent = total
    ? "Where my " + total + " tracked " + (total === 1 ? "job is" : "jobs are") + " right now"
    : "Add jobs to your tracker to see where your applications are.";
  document.getElementById("meters").innerHTML = STAGES.map((stage) => {
    const count = hub.tracker.filter((row) => stage.statuses.includes(row.Status || "Interested")).length;
    const percent = total ? Math.round((count / total) * 100) : 0;
    return '<div class="meter" role="img" aria-label="' + esc(stage.name + ": " + percent + "%, " + count + " of " + total) + '"' +
      ' style="--meter-color: ' + stage.color + '">' +
      '<div class="tube"><div class="fill" style="height: ' + percent + '%"></div></div>' +
      '<div class="bulb"></div>' +
      '<div class="percent">' + percent + "%</div>" +
      '<div class="stage">' + esc(stage.name) + "<br>" + count + " of " + total + "</div>" +
    "</div>";
  }).join("");
  updateToggleButton();
}

// ---------- open and close the tracker table ----------

function updateToggleButton() {
  const open = !document.getElementById("tracker-table").hidden;
  const total = hub.tracker.length;
  const button = document.getElementById("toggle-tracker");
  button.setAttribute("aria-expanded", String(open));
  button.textContent = (open ? "Hide" : "Show") + " my tracker table (" + total + (total === 1 ? " job)" : " jobs)");
}

function showTrackerTable(open) {
  const table = document.getElementById("tracker-table");
  table.hidden = !open;
  updateToggleButton();
  if (open) table.scrollIntoView({ behavior: "smooth", block: "start" });
  else document.getElementById("tracker-section").scrollIntoView({ behavior: "smooth", block: "start" });
}

document.getElementById("toggle-tracker").addEventListener("click", () => {
  showTrackerTable(document.getElementById("tracker-table").hidden);
});
document.getElementById("close-tracker").addEventListener("click", () => showTrackerTable(false));

// ---------- motivation: a new quote every 5 minutes ----------

// Add your own favorites to this list: { text: "...", who: "..." },
const QUOTES = [
  { text: "If there is no struggle, there is no progress.", who: "Frederick Douglass" },
  { text: "Success is to be measured not so much by the position that one has reached in life as by the obstacles which he has overcome.", who: "Booker T. Washington" },
  { text: "If you can't fly then run, if you can't run then walk, if you can't walk then crawl, but whatever you do you have to keep moving forward.", who: "Martin Luther King Jr." },
  { text: "We must accept finite disappointment, but never lose infinite hope.", who: "Martin Luther King Jr." },
  { text: "You may encounter many defeats, but you must not be defeated.", who: "Maya Angelou" },
  { text: "If you want to go fast, go alone. If you want to go far, go together.", who: "African proverb" },
  { text: "However long the night, the dawn will break.", who: "African proverb" },
  { text: "Smooth seas do not make skillful sailors.", who: "African proverb" },
  { text: "Fall seven times, stand up eight.", who: "Japanese proverb" },
  { text: "Little by little, one goes far.", who: "Spanish proverb" },
  { text: "Start where you are. Use what you have. Do what you can.", who: "Arthur Ashe" },
  { text: "The harder the conflict, the more glorious the triumph.", who: "Thomas Paine" },
  { text: "Hard work beats talent when talent doesn't work hard.", who: "Tim Notke" },
  { text: "Don't watch the clock; do what it does. Keep going.", who: "Sam Levenson" },
  { text: "The only way to do great work is to love what you do.", who: "Steve Jobs" },
];
const QUOTE_MINUTES = 5;
let quoteIndex = Math.floor(Math.random() * QUOTES.length);

function showQuote() {
  const box = document.querySelector(".quote-box");
  box.classList.add("fading");
  setTimeout(() => {
    const quote = QUOTES[quoteIndex];
    document.getElementById("quote-text").textContent = quote.text;
    document.getElementById("quote-who").textContent = "— " + quote.who;
    box.classList.remove("fading");
    quoteIndex = (quoteIndex + 1) % QUOTES.length;
  }, 600);
}
showQuote();
setInterval(showQuote, QUOTE_MINUTES * 60 * 1000);

// ---------- all my openings: click a title to jump to it ----------

function drawJumpList() {
  const top = hub.top10.map(jobById).filter(Boolean);
  const others = hub.jobs.filter((job) => !hub.top10.includes(job.id));
  const item = (job, where, extra) =>
    '<li><a href="#' + where + esc(job.id) + '" data-jump="' + where + esc(job.id) + '">' + esc(job.title) + "</a> " +
    '<span class="muted">· ' + esc(job.employer + extra) + "</span></li>";
  document.getElementById("jump-list").innerHTML =
    top.map((job) => item(job, "job-", " · " + job.fit_score + "/10")).join("") +
    others.map((job) => item(job, "other-", " · " + job.label + " (not in top 10)")).join("") ||
    '<li class="muted">No openings yet.</li>';
}

function jumpTo(targetId) {
  const target = document.getElementById(targetId);
  if (!target) return;
  if (target.tagName === "DETAILS") target.open = true;
  const foldOut = target.closest("details:not(.card)");
  if (foldOut) foldOut.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.getElementById("jump-list").addEventListener("click", (event) => {
  const link = event.target.closest("a[data-jump]");
  if (!link) return;
  event.preventDefault();
  jumpTo(link.dataset.jump);
  history.replaceState(null, "", "#" + link.dataset.jump);
});

// ---------- 3. what I'm looking for ----------

function drawProfile() {
  const p = hub.profile;
  const box = document.getElementById("profile");
  if (!p) {
    box.innerHTML = '<p class="muted">No profile yet. Run <code>python agents/build_profile.py</code>.</p>';
    return;
  }
  box.innerHTML =
    "<p>" + esc(p.summary) + "</p>" +
    "<h3>Target roles</h3>" + list(p.target_roles) +
    "<h3>Location</h3><p>" + esc(p.location) + "</p>" +
    "<h3>Must-haves</h3>" + list(p.must_haves) +
    "<h3>Nice-to-haves</h3>" + list(p.nice_to_haves);
}

// ---------- 4. top 10 cards ----------

function labelClass(label) {
  if (label === "good fit") return "good";
  if (label === "maybe") return "maybe";
  if (label === "scam") return "bad";
  return "";
}

function mustHaveLine(check) {
  const marks = { "met": ["✓", "met"], "not met": ["✗", "not-met"], "unknown": ["?", "unknown"] };
  const [mark, cls] = marks[check.status] || ["?", "unknown"];
  return '<li><span class="mark ' + cls + '" aria-label="' + esc(check.status) + '">' + mark + "</span>" +
    "<strong>" + esc(check.must_have) + "</strong> " +
    '<span class="muted">' + esc(check.reason) + "</span></li>";
}

function cardHtml(job, rank) {
  const check = job.student_check || { checked: false, agree: true, note: "" };
  const link = safeLink(job.link);
  // Each card opens and closes. Closed, it shows just the title line.
  return '<details class="card' + (check.checked ? " checked" : "") + '" id="job-' + esc(job.id) +
      '" data-id="' + esc(job.id) + '">' +
    "<summary>" +
      '<div class="card-top">' +
        '<div class="rank" aria-label="Rank ' + rank + '">' + rank + "</div>" +
        "<div><h3>" + esc(job.title) + "</h3>" +
        '<p class="where">' + esc(job.employer) + " · " + esc(job.location) + "</p>" +
        '<p class="where">Pay: ' + esc(job.pay) + "</p></div>" +
        '<div class="score"><strong>' + esc(job.fit_score) + '</strong><span class="muted">/10 fit</span></div>' +
      "</div>" +
      '<div class="chips">' +
        '<span class="chip ' + labelClass(job.label) + '">' + esc(job.label) + "</span>" +
        '<span class="chip">chance: ' + esc(job.chance) + "</span>" +
        '<span class="chip">' + esc(job.source) + "</span>" +
        (job.quick_hire ? '<span class="chip quick">QUICK HIRE</span>' : "") +
        (check.checked ? '<span class="chip good mine">✓ I checked it</span>' : "") +
      "</div>" +
      '<span class="toggle"></span>' +
    "</summary>" +
    '<div class="card-body">' +
    "<p>" + esc(job.why) + "</p>" +
    "<h3>My must-haves</h3>" +
    '<ul class="musts">' + (job.must_haves || []).map(mustHaveLine).join("") + "</ul>" +
    "<h3>Gaps</h3>" + list(job.gaps) +
    '<div class="actions">' +
      (link ? '<a class="button" href="' + esc(link) + '" target="_blank" rel="noopener noreferrer">Open listing</a>'
            : '<span class="muted">No link. Search for this job on the employer\'s site.</span>') +
      '<button type="button" class="secondary" data-action="track">Add to tracker</button>' +
    "</div>" +
    '<div class="my-check">' +
      '<label><input type="checkbox" data-field="checked"' + (check.checked ? " checked" : "") +
        "> I opened it and checked it against my must-haves</label>" +
      '<label>The agent got it… <select data-field="agree">' +
        '<option value="agree"' + (check.agree ? " selected" : "") + ">I agree</option>" +
        '<option value="disagree"' + (check.agree ? "" : " selected") + ">I disagree</option>" +
      "</select></label>" +
      '<textarea data-field="note" aria-label="My note about this job" ' +
        'placeholder="What did the agent get right or wrong? (your own words)">' + esc(check.note) + "</textarea>" +
      '<div><button type="button" data-action="save-check">Save my check</button></div>' +
    "</div>" +
    '<p><a class="back-to-list" href="#jump">↑ Back to all my openings</a></p>' +
    "</div>" +
  "</details>";
}

function drawCards() {
  const box = document.getElementById("cards");
  const topJobs = hub.top10.map(jobById).filter(Boolean);
  box.innerHTML = topJobs.length
    ? topJobs.map((job, i) => cardHtml(job, i + 1)).join("")
    : '<p class="muted">No ranked openings yet. Run <code>python agents/rank_openings.py</code>.</p>';
}

async function saveCheck(card) {
  const id = Number(card.dataset.id);
  const body = {
    id: id,
    checked: card.querySelector('[data-field="checked"]').checked,
    agree: card.querySelector('[data-field="agree"]').value === "agree",
    note: card.querySelector('[data-field="note"]').value,
  };
  const result = await api("/api/check", body);
  jobById(id).student_check = result.student_check;
  card.classList.toggle("checked", result.student_check.checked);
  const chips = card.querySelector(".chips");
  const mine = chips.querySelector(".mine");
  if (mine) mine.remove();
  if (result.student_check.checked) chips.insertAdjacentHTML("beforeend", '<span class="chip good mine">✓ I checked it</span>');
  drawProgress();
  say("Your check is saved. Nice work!");
}

async function addToTracker(card) {
  if (trackerChanged && !confirm("Your tracker has changes you haven't saved. Add this job anyway? (Your unsaved changes will be lost.)")) {
    return;
  }
  const result = await api("/api/tracker/add", { id: Number(card.dataset.id) });
  hub.tracker = result.tracker;
  trackerChanged = false;
  drawTracker();
  drawProgress();
  say(result.added ? "Added to your tracker." : "That job is already in your tracker.");
}

document.getElementById("cards").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest(".card");
  button.disabled = true;
  try {
    if (button.dataset.action === "save-check") await saveCheck(card);
    if (button.dataset.action === "track") await addToTracker(card);
  } catch (err) {
    say(err.message, true);
  } finally {
    button.disabled = false;
  }
});

// ---------- 5. left out ----------

function drawLeftOut() {
  const others = hub.jobs.filter((job) => !hub.top10.includes(job.id));
  document.getElementById("left-out-summary").textContent =
    "Openings that didn't make my top 10 (" + others.length + ")";
  document.getElementById("left-out").innerHTML = others.length
    ? others.map((job) =>
        '<li id="other-' + esc(job.id) + '"><strong>' + esc(job.title) + "</strong> · " + esc(job.employer) + " " +
        '<span class="chip ' + labelClass(job.label) + '">' + esc(job.label) + "</span>" +
        '<br><span class="muted">' + esc(job.why) + "</span></li>").join("")
    : '<li class="muted">None. Every opening made your top 10.</li>';
}

// ---------- 6. tracker ----------

function cellHtml(column, value, rowIndex) {
  const data = 'data-row="' + rowIndex + '" data-col="' + esc(column) + '" aria-label="' + esc(column) + '"';
  if (column === "Status") {
    const options = STATUSES.includes(value) || !value ? STATUSES : STATUSES.concat([value]);
    return "<select " + data + ">" + options.map((s) =>
      '<option value="' + esc(s) + '"' + (s === value ? " selected" : "") + ">" + esc(s) + "</option>").join("") +
      "</select>";
  }
  const type = DATE_COLUMNS.includes(column) ? "date" : "text";
  return '<input type="' + type + '" ' + data + ' value="' + esc(value) + '">';
}

function drawTracker() {
  // A row with no status shows as "Interested", so save it that way too.
  hub.tracker.forEach((row) => { if (!row.Status) row.Status = "Interested"; });
  document.getElementById("tracker-head").innerHTML =
    "<tr>" + COLUMNS.map((c) => "<th>" + esc(c) + "</th>").join("") + "<th>Remove</th></tr>";
  document.getElementById("tracker-body").innerHTML = hub.tracker.map((row, i) =>
    "<tr>" + COLUMNS.map((c) =>
      '<td class="' + (c === "Notes" ? "notes" : "") + '">' + cellHtml(c, row[c] || "", i) + "</td>").join("") +
    '<td><button type="button" class="danger" data-remove="' + i + '">Remove</button></td></tr>'
  ).join("");
  document.getElementById("tracker-empty").textContent = hub.tracker.length
    ? "" : "Your tracker is empty. Use \"Add to tracker\" on a job above, or add a job you found yourself.";
}

const trackerBody = document.getElementById("tracker-body");
trackerBody.addEventListener("input", (event) => {
  const field = event.target;
  if (field.dataset.row === undefined) return;
  hub.tracker[Number(field.dataset.row)][field.dataset.col] = field.value;
  trackerChanged = true;
});
trackerBody.addEventListener("change", () => drawProgress());
trackerBody.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-remove]");
  if (!button) return;
  const row = hub.tracker[Number(button.dataset.remove)];
  const name = [row.Role, row.Company].filter(Boolean).join(" at ") || "this row";
  if (!confirm("Remove " + name + " from your tracker?")) return;
  hub.tracker.splice(Number(button.dataset.remove), 1);
  trackerChanged = true;
  drawTracker();
  drawProgress();
  say("Removed. Click \"Save my tracker\" to keep this change.");
});

document.getElementById("add-row").addEventListener("click", () => {
  const row = {};
  COLUMNS.forEach((c) => { row[c] = ""; });
  row.Status = "Interested";
  hub.tracker.push(row);
  document.getElementById("tracker-table").hidden = false;
  updateToggleButton();
  trackerChanged = true;
  drawTracker();
  drawProgress();
  const inputs = trackerBody.querySelectorAll('input[data-col="Company"]');
  inputs[inputs.length - 1].focus();
});

document.getElementById("save-tracker").addEventListener("click", async (event) => {
  const button = event.target;
  button.disabled = true;
  try {
    const result = await api("/api/tracker", { rows: hub.tracker });
    hub.tracker = result.tracker;
    trackerChanged = false;
    drawTracker();
    drawProgress();
    say("Your tracker is saved.");
  } catch (err) {
    say(err.message, true);
  } finally {
    button.disabled = false;
  }
});

function csvCell(value) {
  let text = String(value == null ? "" : value);
  // Stop spreadsheets from treating a cell as a formula.
  if (/^[=+\-@\t\r]/.test(text)) text = "'" + text;
  return /[",\n\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
}

document.getElementById("download-csv").addEventListener("click", () => {
  const lines = [COLUMNS.map(csvCell).join(",")]
    .concat(hub.tracker.map((row) => COLUMNS.map((c) => csvCell(row[c])).join(",")));
  const blob = new Blob([lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "job-tracker.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  say("Downloaded. In Google Sheets, choose File → Import → Upload.");
});

window.addEventListener("beforeunload", (event) => {
  if (trackerChanged) event.preventDefault();
});

// ---------- 7. documents ----------

const DOC_GROUPS = [
  ["résumés", (doc) => doc.folder === "data" || doc.folder === "resumes"],
  ["cover letters", (doc) => doc.folder === "cover_letters"],
  ["other files", (doc) => doc.folder === "other_files"],
];
const KIND_NAMES = { text: "text", pdf: "PDF", word: "Word" };

function drawDocuments() {
  const listBox = document.getElementById("doc-list");
  let html = "";
  DOC_GROUPS.forEach(([groupName, belongs]) => {
    const docs = hub.documents.map((doc, i) => [doc, i]).filter(([doc]) => belongs(doc));
    if (!docs.length) return;
    html += '<li class="doc-group">' + esc(groupName) + "</li>";
    html += docs.map(([doc, i]) =>
      '<li><button type="button" aria-pressed="false" data-doc="' + i + '">' + esc(doc.title) +
      '<br><span class="muted doc-type">' + esc(KIND_NAMES[doc.kind] || doc.kind) + "</span></button></li>").join("");
  });
  listBox.innerHTML = html || '<li class="muted">No documents yet.</li>';
}

function fileUrl(doc) {
  return "/api/file?" + new URLSearchParams({ folder: doc.folder, name: doc.name }).toString();
}

function downloadUrl(doc, format) {
  return "/api/download?" + new URLSearchParams({ folder: doc.folder, name: doc.name, as: format }).toString();
}

// Download buttons for every document: Word or PDF.
function downloadButtons(doc) {
  const word = doc.kind === "pdf" ? "" :
    '<a class="button" href="' + esc(downloadUrl(doc, "docx")) + '">Download Word (.docx)</a>';
  const pdf = '<a class="button" href="' + esc(downloadUrl(doc, "pdf")) + '">Download PDF</a>';
  let note = "";
  if (doc.kind === "pdf") note = '<p class="muted">Want it in Word? Word can open a PDF directly: in Word, choose File → Open.</p>';
  else note = '<p class="muted">Copies keep your words and paragraphs, not special formatting like tables or pictures.</p>';
  return '<div class="actions">' + word + pdf + "</div>" + note;
}

async function showDocument(doc) {
  const view = document.getElementById("doc-view");
  if (doc.kind === "pdf") {
    view.innerHTML = downloadButtons(doc) +
      '<p><a href="' + esc(fileUrl(doc)) + '" target="_blank" rel="noopener">Open in a new tab</a></p>' +
      '<iframe class="doc-frame" title="' + esc(doc.name) + '" src="' + esc(fileUrl(doc)) + '"></iframe>';
    return;
  }
  if (doc.kind === "word") {
    view.innerHTML = "<p><strong>" + esc(doc.name) + "</strong></p>" + downloadButtons(doc) +
      "<p>Chrome can't show Word files here. Download it and open it in Word or Pages to read, edit, and send it.</p>";
    return;
  }
  view.textContent = "Opening…";
  try {
    const params = new URLSearchParams({ folder: doc.folder, name: doc.name });
    const result = await api("/api/document?" + params.toString());
    view.innerHTML = downloadButtons(doc) + '<pre class="doc-text"></pre>';
    view.querySelector(".doc-text").textContent = result.text;
  } catch (err) {
    view.textContent = err.message;
  }
}

document.getElementById("doc-list").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-doc]");
  if (!button) return;
  document.querySelectorAll("#doc-list button").forEach((b) => b.setAttribute("aria-pressed", "false"));
  button.setAttribute("aria-pressed", "true");
  showDocument(hub.documents[Number(button.dataset.doc)]);
});

// ---------- add a file to my documents ----------

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(new Error("Couldn't read that file. Try choosing it again."));
    reader.readAsDataURL(file);
  });
}

document.getElementById("upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.getElementById("upload-file");
  const file = input.files[0];
  const button = document.getElementById("upload-button");
  if (!file) return say("Choose a file first.", true);
  if (file.size > 10 * 1000 * 1000) return say("That file is bigger than 10 MB. Try a smaller copy.", true);
  button.disabled = true;
  button.textContent = "Adding…";
  try {
    const result = await api("/api/upload", {
      folder: document.getElementById("upload-folder").value,
      name: file.name,
      data: await readAsBase64(file),
    });
    hub.documents = result.documents;
    drawDocuments();
    input.value = "";
    say("Saved " + result.saved + " to your documents.");
  } catch (err) {
    say(err.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Add to my documents";
  }
});

// ---------- start ----------

async function start() {
  try {
    hub = await api("/api/hub");
  } catch (err) {
    say(err.message, true);
    document.getElementById("searching-for").textContent = err.message;
    return;
  }
  drawHeader();
  drawProgress();
  drawJumpList();
  drawProfile();
  drawCards();
  drawLeftOut();
  drawTracker();
  drawDocuments();
}

start();

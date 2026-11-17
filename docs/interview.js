// Interview practice page.
// Mr. Williams reads each question out loud (speechSynthesis), you answer out loud
// (SpeechRecognition) or by typing, and your coach gives STAR feedback through hub.py.
// Every value is escaped before it goes on the page.

"use strict";

const INTERVIEWER = { name: "Mr. Williams", avatar: "👨🏾‍💼", rate: 1.0 }; // rate: 0.85 slower, 1.0 normal, 1.15 faster

let jobs = [];          // my top jobs, from /api/hub
let interviews = [];    // my saved practice sessions, oldest first
let session = null;     // the interview in progress

// Sessions are grouped by job, using the same name they're saved with.
function jobKey(job) {
  return job ? job.title + " · " + job.employer : "General practice";
}

function sessionsFor(key) {
  return interviews.filter((s) => s.job === key);
}

function chosenJob() {
  const choice = $("job-choice").value;
  return jobs.find((j) => String(j.id) === choice) || null;
}

// ---------- small helpers ----------

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
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

const $ = (id) => document.getElementById(id);

// ---------- speaking: the interviewer reads the question ----------

function pickVoice() {
  if (!("speechSynthesis" in window)) return null;
  const voices = speechSynthesis.getVoices();
  return voices.find((v) => v.lang === "en-US" && /male|daniel|alex|aaron|fred|guy/i.test(v.name)) ||
    voices.find((v) => v.lang === "en-US") || voices.find((v) => v.lang.startsWith("en")) || null;
}

function speak(text) {
  if (!("speechSynthesis" in window) || !$("read-aloud").checked) return;
  speechSynthesis.cancel();
  const words = new SpeechSynthesisUtterance(text);
  const voice = pickVoice();
  if (voice) words.voice = voice;
  words.rate = INTERVIEWER.rate;
  speechSynthesis.speak(words);
}

function stopSpeaking() {
  if ("speechSynthesis" in window) speechSynthesis.cancel();
}

// ---------- listening: my answer is typed as I talk ----------

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const NO_MIC = "This browser can't listen. Type your answer, or open this page in Chrome or Edge.";
let listener = null;
let listening = false;
let textBefore = "";   // what was already in the box when I started talking
let heard = "";        // finished phrases from this time talking

function setMic(on) {
  listening = on;
  const button = $("mic-button");
  button.classList.toggle("on", on);
  button.textContent = on ? "⏹ Stop" : "🎤 Answer out loud";
  $("mic-status").textContent = on ? "Listening… talk naturally, then click Stop." : (Recognition ? "" : NO_MIC);
}

function startListening() {
  if (!Recognition) {
    say("This browser can't listen. Please type your answer, or use Chrome or Edge.", true);
    return;
  }
  stopSpeaking();
  listener = new Recognition();
  listener.lang = "en-US";
  listener.continuous = true;
  listener.interimResults = true;
  textBefore = $("answer").value.trim();
  heard = "";
  listener.onresult = (event) => {
    let inProgress = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const piece = event.results[i][0].transcript;
      if (event.results[i].isFinal) heard += piece + " ";
      else inProgress += piece;
    }
    $("answer").value = [textBefore, (heard + inProgress).trim()].filter(Boolean).join(" ");
  };
  listener.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      say("The microphone is blocked. Click the icon in Chrome's address bar to allow it, or type your answer.", true);
    } else if (event.error === "no-speech") {
      say("I didn't hear anything. Check your microphone and try again, or type your answer.", true);
    } else if (event.error !== "aborted") {
      say("Listening stopped (" + event.error + "). You can try again or type your answer.", true);
    }
    setMic(false);
  };
  listener.onend = () => setMic(false);
  try {
    listener.start();
    setMic(true);
  } catch (err) {
    say("Couldn't start the microphone. Please type your answer.", true);
  }
}

function stopListening() {
  if (listener && listening) listener.stop();
  setMic(false);
}

$("mic-button").addEventListener("click", () => (listening ? stopListening() : startListening()));

// ---------- setup ----------

async function loadHub() {
  try {
    const hub = await api("/api/hub");
    const byId = {};
    (hub.jobs || []).forEach((job) => { byId[job.id] = job; });
    jobs = (hub.top10 || []).map((id) => byId[id]).filter(Boolean);
    $("job-choice").innerHTML = '<option value="general">General practice</option>' +
      jobs.map((job) => '<option value="' + esc(job.id) + '">' + esc(job.title + " · " + job.employer) + "</option>").join("");
    interviews = hub.interviews || [];
    drawHistory(interviews);
    drawProgressPicker();
    updateRepeatOption();
  } catch (err) {
    say(err.message, true);
  }
}

// If I've practiced this job before, offer the same questions again so I can compare my scores.
function lastSession(key) {
  const past = sessionsFor(key);
  return past.length ? past[past.length - 1] : null;
}

function updateRepeatOption() {
  const last = lastSession(jobKey(chosenJob()));
  const count = last ? (last.answers || []).length : 0;
  $("repeat-line").hidden = !count;
  if (count) {
    $("repeat-text").textContent = "Ask the same " + count + (count === 1 ? " question" : " questions") +
      " as my last practice for this job, so I can compare my scores";
  }
  $("question-count").disabled = Boolean(count) && $("repeat").checked;
}

$("job-choice").addEventListener("change", updateRepeatOption);
$("repeat").addEventListener("change", updateRepeatOption);

$("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const job = chosenJob();
  const last = lastSession(jobKey(job));
  const repeat = last && !$("repeat-line").hidden && $("repeat").checked
    ? (last.answers || []).map((a) => a.question) : [];
  session = {
    job: job,
    total: repeat.length || Number($("question-count").value),
    repeat: repeat,  // questions to ask again, in the same order
    questions: [],
    answers: [],     // { question, answer, feedback }
  };
  // During the interview, only the interview shows. Scores from past practices come after I finish.
  $("setup").hidden = true;
  $("progress-section").hidden = true;
  $("history-section").hidden = true;
  $("interview").hidden = false;
  $("interviewer-employer").textContent = job ? job.employer : "General practice";
  askNextQuestion();
});

// ---------- the interview ----------

async function askNextQuestion() {
  stopListening();
  $("answer").value = "";
  $("feedback").innerHTML = "";
  $("next-actions").hidden = true;
  $("feedback-button").disabled = true;
  $("question-count-line").textContent = "Question " + (session.questions.length + 1) + " of " + session.total;
  $("question-text").textContent = INTERVIEWER.name + " is thinking of a question…";
  const next = session.repeat[session.questions.length];
  if (next) {  // practicing the same questions again: no need to ask Claude
    session.questions.push(next);
    $("question-text").textContent = next;
    $("feedback-button").disabled = false;
    speak(next);
    return;
  }
  try {
    const result = await api("/api/interview/question", {
      job: session.job ? session.job.id : null,
      asked: session.questions,
    });
    session.questions.push(result.question);
    $("question-text").textContent = result.question;
    $("feedback-button").disabled = false;
    speak(result.question);
  } catch (err) {
    $("question-text").textContent = "Couldn't get a question. " + err.message;
    $("next-actions").hidden = false;
    $("next-button").textContent = "Try again";
  }
}

$("say-again").addEventListener("click", () => {
  const question = session && session.questions[session.questions.length - 1];
  if (!question) return;
  if (!$("read-aloud").checked) $("read-aloud").checked = true;
  speak(question);
});

function starBox(name, part) {
  const ok = part && part.present;
  return '<div class="star-box ' + (ok ? "present" : "missing") + '">' +
    '<div class="star-head"><span class="star-mark">' + (ok ? "✓" : "✗") + "</span> " + esc(name) + "</div>" +
    "<p>" + esc(part ? part.comment : "") + "</p></div>";
}

function drawFeedback(feedback) {
  $("feedback").innerHTML =
    '<div class="score-line">Your STAR score: <strong>' + esc(feedback.score) + "</strong> out of 5</div>" +
    '<div class="star-grid">' +
      starBox("Situation", feedback.situation) + starBox("Task", feedback.task) +
      starBox("Action", feedback.action) + starBox("Result", feedback.result) +
    "</div>" +
    "<h3>What you did well</h3><p>" + esc(feedback.strength) + "</p>" +
    "<h3>Try next time</h3><p>" + esc(feedback.improve) + "</p>" +
    '<details class="stronger"><summary>A stronger version, using only what you said</summary>' +
      '<p class="stronger-text">' + esc(feedback.stronger_version) + "</p></details>";
}

$("feedback-button").addEventListener("click", async () => {
  stopListening();
  stopSpeaking();
  const answer = $("answer").value.trim();
  const question = session.questions[session.questions.length - 1];
  const button = $("feedback-button");
  button.disabled = true;
  $("feedback").innerHTML = '<p class="waiting">Your coach is reading your answer…</p>';
  try {
    const result = await api("/api/interview/feedback", {
      job: session.job ? session.job.id : null,
      question: question,
      answer: answer,
    });
    // One saved answer per question: getting feedback again replaces it.
    const index = session.questions.length - 1;
    session.answers[index] = { question: question, answer: answer, feedback: result.feedback };
    drawFeedback(result.feedback);
    const last = session.questions.length >= session.total;
    $("next-actions").hidden = false;
    $("next-button").hidden = last;
    $("next-button").textContent = "Next question";
  } catch (err) {
    $("feedback").innerHTML = "";
    say(err.message, true);
  } finally {
    button.disabled = false;
  }
});

// Also works as "Try again" if a question didn't come through.
$("next-button").addEventListener("click", () => askNextQuestion());

$("finish-button").addEventListener("click", async () => {
  stopListening();
  stopSpeaking();
  const answers = session.answers.filter(Boolean);
  if (!answers.length) return say("Answer at least one question and get feedback before you save.", true);
  const button = $("finish-button");
  button.disabled = true;
  try {
    const result = await api("/api/interview/save", {
      job_title: session.job ? session.job.title + " · " + session.job.employer : "General practice",
      answers: answers,
    });
    interviews = result.interviews || [];
    const key = jobKey(session.job);
    drawHistory(interviews);
    drawProgressPicker(key);
    say("Saved your practice session. Here's how you did.");
    session = null;
    $("interview").hidden = true;
    $("setup").hidden = false;
    $("progress-section").hidden = false;
    $("history-section").hidden = false;
    updateRepeatOption();
    $("progress-section").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    say(err.message, true);
  } finally {
    button.disabled = false;
  }
});

// ---------- my progress: every practice of one job, side by side ----------

function scoreOf(answer) {
  const score = answer && answer.feedback && answer.feedback.score;
  return typeof score === "number" ? score : null;
}

// The change from my first score to my latest one: ↑ better, ↓ lower, = same.
function change(first, latest, decimals) {
  if (first == null || latest == null) return '<span class="same">–</span>';
  const diff = Number((latest - first).toFixed(decimals || 0));
  const shown = diff.toFixed(decimals || 0);
  if (diff > 0) return '<span class="up">↑ +' + shown + "</span>";
  if (diff < 0) return '<span class="down">↓ ' + shown + "</span>";
  return '<span class="same">= same</span>';
}

function drawProgressPicker(selected) {
  const keys = [];
  interviews.forEach((s) => { if (!keys.includes(s.job)) keys.push(s.job); });
  const pick = selected || (interviews.length ? interviews[interviews.length - 1].job : "");
  $("progress-job").innerHTML = keys.length
    ? keys.map((k) => '<option value="' + esc(k) + '"' + (k === pick ? " selected" : "") + ">" + esc(k) + "</option>").join("")
    : '<option value="">No practice yet</option>';
  drawProgress(pick);
}

$("progress-job").addEventListener("change", () => drawProgress($("progress-job").value));

function drawProgress(key) {
  const past = key ? sessionsFor(key) : [];
  if (!past.length) {
    $("progress-summary").textContent = "Finish a practice interview to see your scores here. " +
      "Then practice the same job again with the same questions to see how you improve.";
    $("progress-head").innerHTML = "";
    $("progress-body").innerHTML = "";
    $("progress-meter-box").hidden = true;
    return;
  }

  // Every question I've been asked for this job, in the order I first saw it.
  const questions = [];
  past.forEach((s) => (s.answers || []).forEach((a) => {
    if (!questions.includes(a.question)) questions.push(a.question);
  }));

  const averages = past.map((s) => Number(average(s.answers)) || null);
  const first = averages[0];
  const previous = averages[averages.length - 2];
  const latest = averages[averages.length - 1];
  if (past.length === 1) {
    $("progress-summary").textContent = "Practice 1 is saved, with an average STAR score of " + average(past[0].answers) +
      " out of 5. Practice this job again with the same questions to see how you improve.";
  } else {
    const diff = Number((latest - previous).toFixed(1));
    const trend = diff > 0 ? "up " + diff.toFixed(1) + ". You're improving. Keep going!"
      : diff < 0 ? "down " + Math.abs(diff).toFixed(1) + ". Look at the questions with ↓ and practice those stories again."
      : "the same. Look at \"Try next time\" in your feedback and aim for one more STAR part.";
    let text = "You've practiced this job " + past.length + " times. Your average STAR score went from " +
      previous.toFixed(1) + " last time to " + latest.toFixed(1) + " this time: " + trend;
    if (past.length > 2) {
      const overall = Number((latest - first).toFixed(1));
      text += overall === 0 ? " That's the same as your first practice (" + first.toFixed(1) + ")."
        : " Since your first practice (" + first.toFixed(1) + "), you're " + (overall > 0 ? "up " : "down ") +
          Math.abs(overall).toFixed(1) + ".";
    }
    $("progress-summary").textContent = text;
  }

  drawMeters(past, averages);

  $("progress-head").innerHTML = "<tr><th>Question</th>" +
    past.map((s, i) => '<th class="score">Practice ' + (i + 1) + '<br><span class="muted">' + esc(s.date) + "</span></th>").join("") +
    '<th class="score">Since last time</th></tr>';

  const rows = questions.map((q) => {
    const scores = past.map((s) => scoreOf((s.answers || []).find((a) => a.question === q)));
    const had = scores.filter((x) => x != null);
    return "<tr><td>" + esc(q) + "</td>" +
      scores.map((x) => '<td class="score">' + (x == null ? '<span class="same">–</span>' : esc(x) + "/5") + "</td>").join("") +
      '<td class="score">' + (had.length > 1 ? change(had[had.length - 2], had[had.length - 1]) : '<span class="same">–</span>') + "</td></tr>";
  });
  rows.push('<tr class="average"><td>Average</td>' +
    averages.map((a) => '<td class="score">' + (a == null ? "–" : esc(a.toFixed(1))) + "</td>").join("") +
    '<td class="score">' + (past.length > 1 ? change(previous, latest, 1) : "–") + "</td></tr>");
  $("progress-body").innerHTML = rows.join("");
}

// One thermometer per practice, filled to my average STAR score out of 5.
function meterColor(score) {
  if (score >= 3.5) return "var(--flag-green)";
  if (score >= 2.5) return "var(--quick)";
  return "var(--flag-red)";
}

function drawMeters(past, averages) {
  $("progress-meter-box").hidden = false;
  $("progress-meters").innerHTML = past.map((s, i) => {
    const score = averages[i] || 0;
    const percent = Math.round((score / 5) * 100);
    const before = i > 0 ? averages[i - 1] : null;
    const arrow = before == null ? "" : "<br>" + change(before, score, 1);
    return '<div class="meter' + (i === past.length - 1 ? " latest" : "") + '" role="img" ' +
      'aria-label="' + esc("Practice " + (i + 1) + ": " + score.toFixed(1) + " out of 5") + '" ' +
      'style="--meter-color: ' + meterColor(score) + '">' +
      '<div class="tube"><div class="fill" style="height: ' + percent + '%"></div></div>' +
      '<div class="bulb"></div>' +
      '<div class="percent">' + esc(score.toFixed(1)) + "</div>" +
      '<div class="stage">Practice ' + (i + 1) + (i === past.length - 1 ? " (latest)" : "") +
        "<br>" + esc(s.date) + arrow + "</div>" +
    "</div>";
  }).join("");
}

// ---------- history ----------

function average(answers) {
  const scores = (answers || []).map((a) => a.feedback && a.feedback.score).filter((s) => typeof s === "number");
  return scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : "–";
}

function drawHistory(interviews) {
  const rows = interviews.slice().sort((a, b) => String(b.date).localeCompare(String(a.date)));
  $("history").innerHTML = rows.length
    ? rows.map((s) => "<tr><td>" + esc(s.date) + "</td><td>" + esc(s.job) + "</td><td>" +
        esc((s.answers || []).length) + "</td><td>" + esc(average(s.answers)) + "</td></tr>").join("")
    : '<tr><td colspan="4" class="muted">No practice sessions yet. Your first one will show up here.</td></tr>';
}

// ---------- start ----------

if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};  // loads the voice list
if (!Recognition) {
  $("mic-button").disabled = true;
  $("mic-status").textContent = NO_MIC;
}
loadHub();

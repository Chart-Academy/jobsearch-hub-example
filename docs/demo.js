// DEMO MODE for the public website.
// The real hub has a Python back end (hub.py) that talks to Claude and saves files.
// This public demo has no back end, so this file stands in for it:
// it loads made-up sample data from demo-data.json and pretends to save in memory only.
// Nothing you do here is saved or sent anywhere, and no AI is used.

"use strict";

(function () {
  const realFetch = window.fetch.bind(window);
  let data = null;

  async function loadData() {
    if (!data) data = await realFetch("demo-data.json").then((r) => r.json());
    return data;
  }

  function reply(value, status) {
    return new Response(JSON.stringify(value), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const DEMO_QUESTIONS = [
    "Tell me a little about yourself and why you want to work in IT support.",
    "Tell me about a time you helped a frustrated customer. What did you do, and how did it turn out?",
    "A staff member calls and says their printer won't print. Walk me through what you would do.",
    "Tell me about a time you learned something new quickly.",
    "How would you explain a password reset to someone who isn't good with computers?",
    "Why do you want to work here, and where do you see yourself in two years?",
  ];

  function demoFeedback(answer) {
    const words = answer.split(/\s+/).filter(Boolean).length;
    const has = (pattern) => pattern.test(answer);
    const parts = {
      situation: has(/\b(when|at my|in my|store|shift|customer|work|team|once|last year)\b/i),
      task: has(/\b(needed|had to|goal|asked to|my job|responsible)\b/i),
      action: has(/\b(I (led|built|met|created|started|planned|trained|asked|worked|made|set|fixed|restarted|checked|called|helped))\b/i),
      result: has(/\b(result|so that|improved|increased|raised|because of|outcome|percent|%)\b/i),
    };
    const score = Math.max(1, Math.min(5, Object.values(parts).filter(Boolean).length + (words > 80 ? 1 : 0)));
    const comment = (ok, yes, no) => ({ present: ok, comment: ok ? yes : no });
    return {
      situation: comment(parts.situation, "You set the scene.", "Start with where you were and what was going on."),
      task: comment(parts.task, "You said what you needed to do.", "Say what your goal or responsibility was."),
      action: comment(parts.action, "You described what you did.", "Walk through the steps you took yourself."),
      result: comment(parts.result, "You shared how it turned out.", "End with the result, ideally with a number."),
      score: score,
      strength: "DEMO FEEDBACK: in the real hub, an AI coach reads your answer. Here, this demo only looks for STAR clue words.",
      improve: "Try telling one specific story with all four parts: Situation, Task, Action, and Result.",
      stronger_version: "In the real hub, this shows your own answer reorganized into STAR order, with [brackets] for details to add.",
      date: new Date().toISOString().slice(0, 10),
    };
  }

  async function demoApi(url, options) {
    const d = await loadData();
    const path = url.pathname;
    const body = options && options.body ? JSON.parse(options.body) : {};

    if (path === "/api/hub") return reply(d);
    if (path === "/api/document") {
      const key = url.searchParams.get("folder") + "/" + url.searchParams.get("name");
      return key in d.document_texts ? reply({ text: d.document_texts[key] }) : reply({ error: "Not in this demo." }, 404);
    }
    if (path === "/api/check") {
      const job = d.jobs.find((j) => j.id === body.id);
      job.student_check = { checked: !!body.checked, agree: body.agree !== false, note: body.note || "" };
      return reply({ saved: true, student_check: job.student_check });
    }
    if (path === "/api/tracker") {
      d.tracker = body.rows || [];
      return reply({ tracker: d.tracker });
    }
    if (path === "/api/tracker/add") {
      const job = d.jobs.find((j) => j.id === body.id);
      const already = d.tracker.some((r) => r.Company === job.employer && r.Role === job.title);
      if (!already) {
        d.tracker.push({ Company: job.employer, Role: job.title, Link: job.link, "QUICK HIRE": job.quick_hire ? "Yes" : "",
          "Date applied": "", Status: "Interested", "Follow-up date": "", "Interview date": "", "Offer date": "", Notes: "" });
      }
      return reply({ tracker: d.tracker, added: !already });
    }
    if (path === "/api/upload") return reply({ error: "Uploads are turned off in this demo. In the real hub they're saved on your own computer." }, 400);
    if (path === "/api/interview/question") {
      const asked = body.asked || [];
      const next = DEMO_QUESTIONS.find((q) => !asked.includes(q)) || DEMO_QUESTIONS[asked.length % DEMO_QUESTIONS.length];
      return reply({ question: next });
    }
    if (path === "/api/interview/feedback") {
      const answer = String(body.answer || "").trim();
      if (answer.length < 15) return reply({ error: "Your answer is a little short. Try again and tell the whole story." }, 400);
      return reply({ feedback: demoFeedback(answer) });
    }
    if (path === "/api/interview/save") {
      d.interviews.push({ date: new Date().toISOString().slice(0, 10), job: body.job_title, answers: body.answers });
      return reply({ saved: "demo", interviews: d.interviews });
    }
    return reply({ error: "That isn't available in this demo." }, 404);
  }

  window.fetch = function (input, options) {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (url.origin === location.origin && url.pathname.startsWith("/api/")) return demoApi(url, options);
    return realFetch(input, options);
  };

  // Download links go to the back end, which this demo doesn't have.
  document.addEventListener("click", (event) => {
    const link = event.target.closest('a[href^="/api/"]');
    if (!link) return;
    event.preventDefault();
    alert("Downloads are turned off in this demo. In the real hub, you can download any document as Word or PDF.");
  });

  // A banner so nobody mistakes this for a real person's job search.
  document.addEventListener("DOMContentLoaded", () => {
    const banner = document.createElement("div");
    banner.className = "demo-banner";
    banner.textContent = "Demo: all data is made up. Saving, uploads, and the AI coach are simulated, and nothing leaves your browser.";
    document.body.prepend(banner);
  });
})();

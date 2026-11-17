"""Fit Checker agent.

Checks every opening in data/openings.json against your profile, labels and
scores it, and saves your top 10 to data/top10.json.

Run it with:  python agents/rank_openings.py
"""

import json

from common import AgentError, RULES, ask, json_of, load_json, run, save_json, today, usage_line

INSTRUCTIONS = RULES + """

Your job: check every job opening against the student's profile.
For each opening (use its id):
- must_haves: check each of the student's must-haves, word for word as they wrote it, as "met",
  "not met", or "unknown", with a short reason. If the listing doesn't say, it is "unknown".
  Unknown is not the same as met.
- label: one of "good fit", "maybe", "not a fit", "scam", "closed", or "duplicate".
  Scam signs: fees or equipment to buy, pay far above normal for the work, asking for bank details
  or an SSN before an interview, interviews only by text or chat app, a vague employer, or a
  personal email address. Use "closed" if the listing says it has closed or its deadline has passed.
  Use "duplicate" if it is the same job as an earlier opening in the list.
- quick_hire: true only if the listing mentions open interviews, same-week interviews or offers,
  on-the-spot hiring, or an immediate start. Otherwise false.
- fit_score: a whole number from 1 to 10.
- chance: "strong", "fair", or "stretch".
  Base fit_score and chance only on how the student's real skills, experience, and certifications
  match the job's requirements. Never assume skills the profile doesn't show.
- why: one or two plain sentences.
- matching_skills: the student's skills that match this job.
- gaps: requirements the student's profile doesn't show."""

LIST_OF_TEXT = {"type": "array", "items": {"type": "string"}}
CHECK = {
    "type": "object",
    "properties": {
        "must_have": {"type": "string"},
        "status": {"type": "string", "enum": ["met", "not met", "unknown"]},
        "reason": {"type": "string"},
    },
    "required": ["must_have", "status", "reason"],
    "additionalProperties": False,
}
RANKING = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "must_haves": {"type": "array", "items": CHECK},
        "label": {"type": "string",
                  "enum": ["good fit", "maybe", "not a fit", "scam", "closed", "duplicate"]},
        "quick_hire": {"type": "boolean"},
        "fit_score": {"type": "integer"},
        "chance": {"type": "string", "enum": ["strong", "fair", "stretch"]},
        "why": {"type": "string"},
        "matching_skills": LIST_OF_TEXT,
        "gaps": LIST_OF_TEXT,
    },
    "required": ["id", "must_haves", "label", "quick_hire", "fit_score", "chance", "why",
                 "matching_skills", "gaps"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {"rankings": {"type": "array", "items": RANKING}},
    "required": ["rankings"],
    "additionalProperties": False,
}


def main():
    profile = load_json("profile.json")
    openings = load_json("openings.json")["openings"]
    if not openings:
        raise AgentError("data/openings.json has no openings yet. Run python agents/find_openings.py first.")

    # The parts of your profile the checker needs.
    about_you = {key: profile[key] for key in
                 ["summary", "target_roles", "location", "skills", "hidden_skills",
                  "certifications", "must_haves", "nice_to_haves", "start_date"]}

    print("Checking " + str(len(openings)) + " openings against your profile... (about a minute)")
    content = ("Today is " + today() + ".\n\n<profile>\n" + json.dumps(about_you, indent=2)
               + "\n</profile>\n\n<openings>\n" + json.dumps(openings, indent=2) + "\n</openings>")
    response = ask(INSTRUCTIONS, [{"role": "user", "content": content}], schema=SCHEMA, max_tokens=16000)
    rankings = {r["id"]: r for r in json_of(response)["rankings"]}

    jobs = []
    for opening in openings:
        ranking = rankings.get(opening["id"])
        if ranking is None:
            continue
        job = dict(opening)
        job.update(ranking)
        job["fit_score"] = max(1, min(10, job["fit_score"]))
        job["student_check"] = {"checked": False, "agree": True, "note": ""}
        jobs.append(job)

    order = {"good fit": 0, "maybe": 1}
    jobs.sort(key=lambda j: (order.get(j["label"], 2), -j["fit_score"]))
    top10 = [j["id"] for j in jobs if j["label"] in order][:10]

    save_json("top10.json", {"updated": today(), "top10": top10, "jobs": jobs})

    print()
    print("Your top " + str(len(top10)) + " (saved to data/top10.json):")
    print()
    by_id = {j["id"]: j for j in jobs}
    for rank, job_id in enumerate(top10, start=1):
        job = by_id[job_id]
        quick = "  QUICK HIRE" if job["quick_hire"] else ""
        print(str(rank) + ". " + job["title"] + " - " + job["employer"])
        print("   Fit " + str(job["fit_score"]) + "/10 | " + job["label"] + " | chance: " + job["chance"] + quick)
        print("   " + job["why"])
        for check in job["must_haves"]:
            mark = {"met": "✓", "not met": "✗", "unknown": "?"}[check["status"]]
            print("     " + mark + " " + check["must_have"] + " - " + check["reason"])
        print()

    left_out = [j for j in jobs if j["id"] not in top10]
    if left_out:
        print("Left out of your top 10:")
        for job in left_out:
            print("  - " + job["title"] + " - " + job["employer"] + " (" + job["label"] + "): " + job["why"])
        print()

    print("These scores are estimates. Open every listing and check it against your must-haves yourself.")
    print()
    print("Next step: build the back end of your Job Search Hub (Prompt 7).")
    print(usage_line(response))


if __name__ == "__main__":
    run(main)

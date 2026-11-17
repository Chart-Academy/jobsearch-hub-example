"""Profile Builder agent.

Reads data/resume.txt and data/about_me.md and saves a skills profile
to data/profile.json. The other agents use this profile to find and rank jobs.

Run it with:  python agents/build_profile.py
"""

from common import DATA, RULES, ask, json_of, read, run, save_json, today, usage_line

INSTRUCTIONS = RULES + """

Your job: build the student's skills profile from their résumé and their "about me" notes.
- summary: two sentences about who they are and what they want next.
- target_roles: the jobs they say they want, using their words.
- location: where they want to work and how they get there.
- skills: skills shown in the résumé or notes. For each one, "proof" says where it shows up
  (for example, "Résumé: job title at employer" or "About me: anything else").
- hidden_skills: skills the student clearly has but didn't list as skills, drawn only from what
  the files actually say (for example from caregiving, volunteering, side jobs, or the duties they
  describe). Give the proof for each one too. If there are none, return an empty list.
- certifications: only certifications or licenses the files name. Never add any.
- must_haves: copy each must-have exactly as the student wrote it, word for word.
- nice_to_haves: copy each nice-to-have as the student wrote it.
- start_date: when they can start, in their words.
- search_terms: 3 to 5 job titles or keywords to search job boards with.
- notes_still_sample: true if any line in about_me.md still starts with "SAMPLE"."""

SKILL = {
    "type": "object",
    "properties": {"skill": {"type": "string"}, "proof": {"type": "string"}},
    "required": ["skill", "proof"],
    "additionalProperties": False,
}
LIST_OF_TEXT = {"type": "array", "items": {"type": "string"}}

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "target_roles": LIST_OF_TEXT,
        "location": {"type": "string"},
        "skills": {"type": "array", "items": SKILL},
        "hidden_skills": {"type": "array", "items": SKILL},
        "certifications": LIST_OF_TEXT,
        "must_haves": LIST_OF_TEXT,
        "nice_to_haves": LIST_OF_TEXT,
        "start_date": {"type": "string"},
        "search_terms": LIST_OF_TEXT,
        "notes_still_sample": {"type": "boolean"},
    },
    "required": [
        "summary", "target_roles", "location", "skills", "hidden_skills", "certifications",
        "must_haves", "nice_to_haves", "start_date", "search_terms", "notes_still_sample",
    ],
    "additionalProperties": False,
}


def still_sample(notes):
    """True if any answer line in about_me.md still starts with SAMPLE."""
    for line in notes.splitlines():
        if line.strip().lstrip("- ").startswith("SAMPLE"):
            return True
    return False


def bullets(items):
    return "\n".join("  - " + item for item in items) or "  (none)"


def main():
    resume = read(DATA / "resume.txt")
    notes = read(DATA / "about_me.md")

    print("Building your profile... (this takes about a minute)")
    response = ask(
        INSTRUCTIONS,
        [{
            "role": "user",
            "content": "<resume>\n" + resume + "\n</resume>\n\n<about_me>\n" + notes + "\n</about_me>",
        }],
        schema=SCHEMA,
    )
    profile = json_of(response)
    # Double-check the SAMPLE lines ourselves, so this answer is always right.
    profile["notes_still_sample"] = still_sample(notes)
    profile["updated"] = today()
    save_json("profile.json", profile)

    print()
    print("Your profile is saved in data/profile.json.")
    print()
    print(profile["summary"])
    print()
    print("What you're looking for:")
    print(bullets(profile["target_roles"]))
    print("  Where: " + profile["location"])
    print("  Start: " + profile["start_date"])
    print()
    print("Your must-haves:")
    print(bullets(profile["must_haves"]))
    print()
    print("Your skills:")
    print(bullets([s["skill"] + "  (" + s["proof"] + ")" for s in profile["skills"]]))
    print()
    print("Hidden skills (ones you have but didn't list):")
    print(bullets([s["skill"] + "  (" + s["proof"] + ")" for s in profile["hidden_skills"]]))
    print()
    if profile["notes_still_sample"]:
        print("Heads up: data/about_me.md still has SAMPLE lines. Finish it in your own words,")
        print("then run this agent again.")
        print()
    print("Next step: check that everything above is true. Then build the Opening Finder (Prompt 5).")
    print(usage_line(response))


if __name__ == "__main__":
    run(main)

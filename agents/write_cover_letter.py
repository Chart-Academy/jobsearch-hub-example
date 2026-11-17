"""Cover Letter agent.

Drafts a cover letter for one job from your top 10, using only your real
experience from your résumé. It saves the draft to data/cover_letters/ so you
can read and edit it in your hub (My documents).

Run it with the job's id number, for example:  python agents/write_cover_letter.py 3
"""

import sys

from common import AgentError, DATA, RULES, ask, json_of, load_json, read, run, slug, usage_line

INSTRUCTIONS = RULES + """

Your job: draft a cover letter for one job, for the student to edit and send themselves.
- Under 250 words for the whole letter, including the greeting and sign-off.
- Use only experience, skills, results, and certifications that are in the student's résumé
  and profile. Never invent anything, and never add numbers or results that aren't there.
- Connect the student's real experience to what this job asks for.
- Put [brackets] where the student should add something only they know, for example
  [the hiring manager's name], [why this organization matters to you], or [a short story about ...].
- Don't make up the hiring manager's name, the employer's address, or the date.
- Sound warm, confident, and professional, in plain language. No clichés.
- Return only the letter itself in "letter": greeting, body, and sign-off with the student's name."""

SCHEMA = {
    "type": "object",
    "properties": {"letter": {"type": "string"}},
    "required": ["letter"],
    "additionalProperties": False,
}


def job_id_from_command_line():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise AgentError("Tell me which job, by its id number. For example: python agents/write_cover_letter.py 3")
    return int(sys.argv[1])


def free_path(name):
    """A file name in data/cover_letters/ that doesn't exist yet, so earlier drafts are never overwritten."""
    folder = DATA / "cover_letters"
    path = folder / (name + ".md")
    number = 2
    while path.exists() or path.with_suffix(".docx").exists():
        path = folder / (name + "-" + str(number) + ".md")
        number += 1
    return path


def save_docx(path, letter):
    """Save the letter as a Word file you can open in Word or Pages, edit, and send."""
    from docx import Document
    from docx.shared import Pt, RGBColor

    document = Document()
    style = document.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    warning = document.add_paragraph().add_run("DRAFT: edit before you send. (Delete this line when you're done.)")
    warning.bold = True
    warning.font.color.rgb = RGBColor(0xC8, 0x10, 0x2E)
    for block in letter.split("\n\n"):
        document.add_paragraph(block.strip())
    document.save(str(path))


def main():
    job_id = job_id_from_command_line()
    jobs = load_json("top10.json")["jobs"]
    job = next((j for j in jobs if j.get("id") == job_id), None)
    if job is None:
        ids = ", ".join(str(j["id"]) for j in jobs)
        raise AgentError("There's no job with id " + str(job_id) + ". The ids in data/top10.json are: " + ids)

    resume = read(DATA / "resume.txt")
    profile = load_json("profile.json", required=False) or {}

    the_job = "\n".join([
        "Title: " + job["title"],
        "Employer: " + job["employer"],
        "Location: " + job["location"],
        "About the job: " + job["about"],
        "Requirements: " + "; ".join(job.get("requirements", [])),
        "Skills of mine that match (from my fit check): " + "; ".join(job.get("matching_skills", [])),
    ])
    my_profile = "\n".join([
        "Certifications: " + "; ".join(profile.get("certifications", [])),
        "Summary: " + profile.get("summary", ""),
    ])

    print("Drafting a cover letter for " + job["title"] + " at " + job["employer"] + "...")
    response = ask(
        INSTRUCTIONS,
        [{"role": "user", "content": "<job>\n" + the_job + "\n</job>\n\n<resume>\n" + resume
          + "\n</resume>\n\n<profile>\n" + my_profile + "\n</profile>"}],
        schema=SCHEMA,
    )
    letter = json_of(response)["letter"].strip()
    words = len(letter.split())

    path = free_path(slug(job["employer"] + " " + job["title"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "DRAFT: edit before you send.\n\n"
        "# Cover letter: " + job["title"] + " at " + job["employer"] + "\n\n"
        + letter + "\n",
        encoding="utf-8",
    )
    docx_path = path.with_suffix(".docx")
    save_docx(docx_path, letter)

    print()
    print(letter)
    print()
    print("Saved to " + str(path.relative_to(DATA.parent)) + " (" + str(words) + " words).")
    print("Word copy to edit and send: " + str(docx_path.relative_to(DATA.parent)))
    if words >= 250:
        print("Heads up: it's " + str(words) + " words. Trim it to under 250 when you edit.")
    print()
    print("Next step: open it in your hub (My documents), fill in every [bracket], and edit it")
    print("until it's true and sounds like you. You send it yourself.")
    print(usage_line(response))


if __name__ == "__main__":
    run(main)

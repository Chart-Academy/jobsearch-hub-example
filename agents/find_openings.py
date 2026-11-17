"""Opening Finder agent.

Finds real, current job openings that fit your profile (with Claude's web search),
adds the listings you pasted into data/listings_pasted.txt, and saves them all
to data/openings.json.

Run it with:  python agents/find_openings.py
Only your pasted listings, no web search:  python agents/find_openings.py --no-search
"""

import sys

from common import (AgentError, DATA, RULES, ask, json_of, load_json, read, run, save_json,
                    text_of, today, usage_line)

WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}

SEARCH_INSTRUCTIONS = RULES + """

Your job: search the web for real, current job openings that fit the student's profile.
- Search for their target roles and search terms near their location.
- Prefer employer career pages, government job boards (USAJOBS, DC Government Careers),
  and well-known job boards.
- Senior school leadership jobs are mostly posted by the employers themselves. Look at the career
  pages of school districts and education agencies in the student's area (for the D.C. area:
  DC Public Schools, OSSE, DC public charter schools, Montgomery County, Arlington, Alexandria,
  Fairfax County, and Prince George's County public schools), education nonprofits, and education
  job boards such as K12JobSpot, SchoolSpring, EdJoin, and the Idealist nonprofit board.
- Report single openings at a named employer. Don't report a search-results page or a page that
  lists many jobs as an opening.
- For each opening, write down: title, employer, location, pay, schedule, the link exactly as it
  appeared in the search results, when it was posted, two or three lines about the job, and any
  sign of fast hiring (open interviews, same-week offers, immediate start).
- Only report openings you actually saw in the search results. Never make up a link or a detail;
  if something isn't shown, write "not listed".
- Aim for 10 to 15 openings.
- Never log in to any site and never apply for a job."""

ORGANIZE_INSTRUCTIONS = RULES + """

Your job: turn the web search notes and the student's pasted listings into one clean list.
- source is "web search" for openings from the search notes and "you pasted" for the student's own.
- link: copy it exactly from the notes or the pasted listing. If there is no link, use "".
  Never make one up.
- If a detail isn't given, write "not listed". Don't guess pay, schedule, or dates.
- about: two or three plain sentences about the job.
- requirements: the requirements the listing states.
- fast_hire_signs: open interviews, same-week interviews or offers, on-the-spot hiring, immediate start.
- warning_signs: anything that looks like a scam (fees, equipment to buy, pay far above normal,
  asking for bank details or an SSN up front, interviews only by text or chat app, a vague employer,
  a personal email address), or signs the listing is closed or old.
- Merge exact duplicates (same job at the same employer) into one.
- Number the openings with id, starting at 1."""

LIST_OF_TEXT = {"type": "array", "items": {"type": "string"}}
OPENING = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "string"},
        "employer": {"type": "string"},
        "location": {"type": "string"},
        "pay": {"type": "string"},
        "schedule": {"type": "string"},
        "link": {"type": "string"},
        "posted": {"type": "string"},
        "source": {"type": "string", "enum": ["web search", "you pasted"]},
        "about": {"type": "string"},
        "requirements": LIST_OF_TEXT,
        "fast_hire_signs": LIST_OF_TEXT,
        "warning_signs": LIST_OF_TEXT,
    },
    "required": ["id", "title", "employer", "location", "pay", "schedule", "link", "posted",
                 "source", "about", "requirements", "fast_hire_signs", "warning_signs"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {"openings": {"type": "array", "items": OPENING}},
    "required": ["openings"],
    "additionalProperties": False,
}


def pasted_listings():
    """Your own listings, or "" if the file still has the sample note at the top."""
    text = read(DATA / "listings_pasted.txt", required=False).strip()
    if text.startswith("PASTE LISTINGS YOU FOUND YOURSELF") or "SAMPLE LISTING" in text:
        return ""
    return text


def search(profile):
    """Step 1: Claude searches the web. Returns (response, notes, links seen)."""
    request = (
        "Today is " + today() + ". Find current openings for this job seeker.\n\n"
        "Target roles: " + ", ".join(profile["target_roles"]) + "\n"
        "Search terms: " + ", ".join(profile["search_terms"]) + "\n"
        "Location: " + profile["location"] + "\n"
        "Must-haves: " + "; ".join(profile["must_haves"])
    )
    response = ask(SEARCH_INSTRUCTIONS, [{"role": "user", "content": request}],
                   tools=[WEB_SEARCH], effort="low")
    seen = set()
    for block in response.content:
        if block.type == "web_search_tool_result" and isinstance(block.content, list):
            for result in block.content:
                if getattr(result, "url", None):
                    seen.add(result.url)
    return response, text_of(response), seen


def main():
    use_search = "--no-search" not in sys.argv
    profile = load_json("profile.json")
    pasted = pasted_listings()
    if not pasted:
        print("Skipping data/listings_pasted.txt (it still has the sample note, or it's empty).")
    if not use_search and not pasted:
        raise AgentError("You ran with --no-search, but you haven't pasted any listings yet. "
                         "Add some to data/listings_pasted.txt and try again.")

    responses = []
    notes, seen = "", set()
    if use_search:
        print("Searching the web for openings... (this can take a few minutes)")
        response, notes, seen = search(profile)
        responses.append(response)
        # Keep the search notes so you can see what the search found.
        (DATA / "search_notes.txt").write_text(notes + "\n", encoding="utf-8")

    print("Organizing the openings...")
    content = ("<web_search_notes>\n" + (notes or "(no web search this time)") + "\n</web_search_notes>\n\n"
               "<pasted_listings>\n" + (pasted or "(none)") + "\n</pasted_listings>")
    response = ask(ORGANIZE_INSTRUCTIONS, [{"role": "user", "content": content}], schema=SCHEMA)
    responses.append(response)
    openings = json_of(response)["openings"]

    # Safety check: keep a link only if it really came from the search results or your listings.
    for number, job in enumerate(openings, start=1):
        job["id"] = number
        link = job["link"].strip()
        if link and link not in seen and link not in notes and link not in pasted:
            job["link"] = ""
            job["warning_signs"].append("The link couldn't be confirmed, so it was removed. Search for this job yourself.")

    save_json("openings.json", {"updated": today(), "openings": openings})

    print()
    print("Found " + str(len(openings)) + " openings. Saved to data/openings.json.")
    print()
    for job in openings:
        print(str(job["id"]) + ". " + job["title"] + " - " + job["employer"])
        print("   " + job["location"] + " | Pay: " + job["pay"] + " | Posted: " + job["posted"]
              + " | " + job["source"])
        print("   " + (job["link"] or "(no link)"))
        if job["fast_hire_signs"]:
            print("   Fast hiring: " + "; ".join(job["fast_hire_signs"]))
        if job["warning_signs"]:
            print("   Watch out: " + "; ".join(job["warning_signs"]))
    print()
    print("Remember: open each link yourself to make sure the job is real and still open.")
    print("The agent never logs in or applies for you.")
    print()
    print("Next step: add two or three listings you found yourself to data/listings_pasted.txt,")
    print("then build the Fit Checker (Prompt 6).")
    print(usage_line(*responses))


if __name__ == "__main__":
    run(main)

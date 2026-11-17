# Job Search Hub: class example

An example of the Job Search Hub from Chart Academy's Agent Labs (WO-04 and WO-05), shared so classmates can see one finished version.

**All the data in `data/` is made up.** "Jordan Sample" and every employer, job, and interview answer are fictional, and every link goes to example.com. No real person's information is in this repo.

## What's in it
- **Agents** (`agents/`), which use the Claude API:
  - `build_profile.py`: turns a résumé and "about me" notes into a skills profile.
  - `find_openings.py`: searches the web for openings (school districts and education job boards).
  - `rank_openings.py`: checks each opening against your must-haves and picks a top 10.
  - `write_cover_letter.py <id>`: drafts a cover letter (Markdown and Word) using only real experience.
  - `interview_coach.py`: asks interview questions and gives STAR feedback.
- **The hub** (`hub.py` + `site/`): a private website that runs only on your own computer.
  - Jobs page: red, black, and green colors; tracker thermometers at the top left; a clickable list of openings; job cards that open and close; a motivational quote that changes every 5 minutes; and document uploads with Word or PDF downloads.
  - Interview practice: Mr. Williams 👨🏾‍💼 reads questions out loud, you answer out loud (Chrome) or type, and you get STAR feedback. You can practice the same questions again and see your progress on thermometers and in a question-by-question table.

## Try it on your computer
1. Python 3.9 or newer. In this folder:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   On Windows, activate it with `.venv\Scripts\Activate.ps1`.
2. Copy `.env.example` to `.env` and paste **your own** Claude API key after `ANTHROPIC_API_KEY=`. Never share your key or commit `.env`.
3. Start the hub with `python hub.py`, then open http://localhost:8000 in Chrome.

The sample data shows up right away. The agents and the interview coach use your API key and your class budget, so keep test runs small.

## Make it yours
Replace the files in `data/` with your own résumé and notes. If your repo is public, leave your personal files out, and never include a Social Security number, birth date, home address, or bank details. The class prompts are in `prompts/`.

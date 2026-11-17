"""Interview Coach agent.

Two helpers the hub uses for interview practice:
- next_question(job, asked): one interview question, as a friendly hiring manager would ask it.
- star_feedback(job, question, answer): STAR feedback (Situation, Task, Action, Result) on one answer.

Try it in the terminal:  python agents/interview_coach.py
It asks one general question, you type your answer, and it prints your STAR feedback.
"""

from common import RULES, AgentError, ask, json_of, run, text_of, today, usage_line

QUESTION_INSTRUCTIONS = RULES + """

You are a friendly hiring manager interviewing the student for a job.
Ask exactly ONE interview question.
- One or two short sentences that sound natural when read out loud. No lists, no numbering.
- Mix common questions (like "Tell me about yourself"), behavioral questions (like "Tell me about a time
  you..."), and questions about the job's real requirements.
- Never repeat or reword a question that was already asked.
- Reply with the question only: no greeting, no explanation, no quotation marks."""

FEEDBACK_INSTRUCTIONS = RULES + """

You are a warm, honest interview coach. Score the student's answer to one interview question using
STAR: Situation, Task, Action, Result.
- The answer was spoken out loud and turned into text, so ignore filler words ("um", "like") and small
  transcription mistakes.
- For situation, task, action, and result: present is true only if the answer really includes that part.
  The comment says briefly what they said or what is missing.
- score: 1 = no STAR parts, 5 = all four parts, clear and specific.
- strength: one or two sentences on what they did well.
- improve: one or two sentences on the most useful thing to try next time.
- stronger_version: reorganize ONLY what the student actually said into STAR order, in their voice.
  Put [brackets] wherever they need to add something from their own experience, like
  [what the result was] or [a number that shows the impact]. Never add experience, numbers, results,
  or details they didn't mention."""

STAR_PART = {
    "type": "object",
    "properties": {"present": {"type": "boolean"}, "comment": {"type": "string"}},
    "required": ["present", "comment"],
    "additionalProperties": False,
}
FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "situation": STAR_PART,
        "task": STAR_PART,
        "action": STAR_PART,
        "result": STAR_PART,
        "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "strength": {"type": "string"},
        "improve": {"type": "string"},
        "stronger_version": {"type": "string"},
    },
    "required": ["situation", "task", "action", "result", "score", "strength", "improve", "stronger_version"],
    "additionalProperties": False,
}


def describe_job(job):
    """The job, written out for Claude. job is one job from data/top10.json, or None."""
    if not job:
        return "A general entry-level job (no specific employer)."
    lines = ["Job title: " + str(job.get("title", "")), "Employer: " + str(job.get("employer", ""))]
    if job.get("about"):
        lines.append("About the job: " + str(job["about"]))
    if job.get("requirements"):
        lines.append("Requirements: " + "; ".join(str(r) for r in job["requirements"]))
    return "\n".join(lines)


def next_question(job, asked):
    """One new interview question for this job (or a general one if job is None), as plain text."""
    asked = [str(q) for q in (asked or [])]
    already = "\n".join("- " + q for q in asked) if asked else "(none yet)"
    content = ("<job>\n" + describe_job(job) + "\n</job>\n\n"
               "<already_asked>\n" + already + "\n</already_asked>\n\n"
               "Ask question number " + str(len(asked) + 1) + ".")
    response = ask(QUESTION_INSTRUCTIONS, [{"role": "user", "content": content}],
                   effort="low", max_tokens=1000)
    question = text_of(response).strip().strip('"').strip()
    if not question:
        raise AgentError("The interviewer didn't come up with a question. Please try again.")
    return question


def feedback_with_usage(job, question, answer):
    """STAR feedback plus the Claude response (so the terminal can show tokens used)."""
    content = ("<job>\n" + describe_job(job) + "\n</job>\n\n"
               "<question>\n" + str(question) + "\n</question>\n\n"
               "<spoken_answer>\n" + str(answer) + "\n</spoken_answer>")
    response = ask(FEEDBACK_INSTRUCTIONS, [{"role": "user", "content": content}],
                   schema=FEEDBACK_SCHEMA, effort="low", max_tokens=3000)
    feedback = json_of(response)
    feedback["date"] = today()
    return feedback, response


def star_feedback(job, question, answer):
    """STAR feedback on one answer, as a dict (with today's date added as "date")."""
    return feedback_with_usage(job, question, answer)[0]


def print_feedback(feedback):
    print()
    print("Your STAR score: " + str(feedback["score"]) + " out of 5")
    print()
    for part in ["situation", "task", "action", "result"]:
        mark = "✓" if feedback[part]["present"] else "✗"
        print("  " + mark + " " + part.capitalize() + ": " + feedback[part]["comment"])
    print()
    print("What you did well: " + feedback["strength"])
    print("Try next time: " + feedback["improve"])
    print()
    print("A stronger version, using only what you said:")
    print(feedback["stronger_version"])
    print()


def main():
    print("Getting a question from your interviewer...")
    question = next_question(None, [])
    print()
    print("Interviewer: " + question)
    print()
    answer = input("Your answer (type it, then press Return):\n> ").strip()
    if len(answer) < 15:
        raise AgentError("That answer is very short. Run it again and tell the whole story.")
    print()
    print("Your coach is reading your answer...")
    feedback, response = feedback_with_usage(None, question, answer)
    print_feedback(feedback)
    print("Next step: add interview practice to your hub (Prompt 3).")
    print(usage_line(response))


if __name__ == "__main__":
    run(main)

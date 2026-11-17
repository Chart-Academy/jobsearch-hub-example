"""Job Search Hub: the back end.

A small web server that runs only on this computer. It shows the pages in site/
and has a small JSON API under /api/ that reads and saves your files in data/.

Start it in a second terminal window:  python hub.py
Stop it with Ctrl+C.
"""

import base64
import csv
import io
import json
import os
import re
import threading
import zipfile
from functools import partial
from xml.etree import ElementTree
from xml.sax.saxutils import escape as xml_escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

HOST = "127.0.0.1"
PORT = 8000
REPO = Path(__file__).resolve().parent
DATA = REPO / "data"
SITE = REPO / "site"

TRACKER = DATA / "tracker.csv"
COLUMNS = ["Company", "Role", "Link", "QUICK HIRE", "Date applied", "Status",
           "Follow-up date", "Interview date", "Offer date", "Notes"]

# The folders the documents list can show. "data" only ever shows resume.txt.
FOLDERS = {"data": DATA, "resumes": DATA / "resumes", "cover_letters": DATA / "cover_letters",
           "other_files": DATA / "other_files"}
UPLOAD_FOLDERS = ["resumes", "cover_letters", "other_files"]

# The kinds of documents the hub keeps. Text shows on the page; PDF and Word open or download.
TEXT_TYPES = (".md", ".txt")
FILE_TYPES = {".pdf": "application/pdf",
              ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
KINDS = {".md": "text", ".txt": "text", ".pdf": "pdf", ".docx": "word"}

MAX_BODY = 1_000_000          # 1 MB is plenty for a tracker or a note
MAX_UPLOAD = 10_000_000       # uploaded files can be up to 10 MB
SAVE_LOCK = threading.Lock()  # one save at a time


class HubError(Exception):
    """A problem explained in plain language, sent back as {"error": ...}."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ---------- reading and saving files ----------

def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise HubError("The file " + path.name + " is damaged. Run the agent that makes it again.", 500)


def write_text(path, text):
    """Save safely: write a temporary file first, then swap it in."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(temp, path)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_top10():
    return read_json(DATA / "top10.json", {"updated": "", "top10": [], "jobs": []})


def load_tracker():
    if not TRACKER.exists():
        return []
    with TRACKER.open(encoding="utf-8", newline="") as f:
        return [{col: (row.get(col) or "") for col in COLUMNS} for row in csv.DictReader(f)]


def save_tracker(rows):
    path = TRACKER
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def clean_rows(rows):
    """Keep only the tracker columns, as text."""
    if not isinstance(rows, list):
        raise HubError("The tracker should be a list of rows.")
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            raise HubError("Each tracker row should have the tracker columns.")
        cleaned.append({col: str(row.get(col) or "").strip() for col in COLUMNS})
    return cleaned


def doc_title(path):
    """The first heading in the file, or a tidy version of the file name."""
    if path == DATA / "resume.txt":
        return "My résumé"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        pass
    return path.stem.replace("-", " ").replace("_", " ").capitalize()


def list_documents():
    docs = []
    if (DATA / "resume.txt").exists():
        docs.append({"folder": "data", "name": "resume.txt", "title": "My résumé", "kind": "text"})
    for folder in UPLOAD_FOLDERS:
        base = FOLDERS[folder]
        if base.is_dir():
            for path in sorted(base.iterdir()):
                kind = KINDS.get(path.suffix.lower())
                if kind and path.is_file() and not path.name.startswith("."):
                    title = doc_title(path) if kind == "text" else path.name
                    docs.append({"folder": folder, "name": path.name, "title": title, "kind": kind})
    return docs


def list_interviews():
    folder = DATA / "interviews"
    interviews = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            try:
                interviews.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue  # skip a damaged file instead of breaking the page
    return interviews


# ---------- the API ----------

def get_hub():
    top = load_top10()
    return {
        "profile": read_json(DATA / "profile.json", None),
        "top10": top.get("top10", []),
        "jobs": top.get("jobs", []),
        "updated": top.get("updated", ""),
        "tracker": load_tracker(),
        "documents": list_documents(),
        "interviews": list_interviews(),
    }


def document_path(query):
    """The path of one of your documents, after checking it's safe to open."""
    folder = (query.get("folder") or [""])[0]
    name = (query.get("name") or [""])[0]
    if folder not in FOLDERS:
        raise HubError("That folder isn't one of your document folders.")
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise HubError("That isn't a document name the hub can open.")
    if folder == "data" and name != "resume.txt":
        raise HubError("That isn't one of your documents.")
    if Path(name).suffix.lower() not in KINDS:
        raise HubError("The hub only opens .md, .txt, .pdf, and .docx documents.")
    path = FOLDERS[folder] / name
    if not path.is_file():
        raise HubError("Can't find that document. It may have been moved or renamed.", 404)
    return path


def get_document(query):
    path = document_path(query)
    if path.suffix.lower() not in TEXT_TYPES:
        raise HubError("That's a PDF or Word file. Use Open or Download instead.")
    return {"text": path.read_text(encoding="utf-8")}


# ---------- making Word and PDF copies (standard library only) ----------
# A document is turned into a simple list of blocks: ("h", heading), ("p", text), or ("blank", "").
# The copies keep the words and paragraphs, not fancy formatting like tables or pictures.

def text_blocks(text, markdown):
    blocks = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            blocks.append(("blank", ""))
        elif markdown and stripped.startswith("#"):
            blocks.append(("h", stripped.lstrip("#").strip()))
        else:
            if markdown:
                stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
                if stripped.startswith(("- ", "* ")):
                    stripped = "• " + stripped[2:]
            blocks.append(("p", stripped))
    return blocks


WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_blocks(path):
    """The paragraphs of a Word file, read straight from the file."""
    try:
        with zipfile.ZipFile(path) as package:
            xml = package.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        raise HubError("That Word file couldn't be read. Try opening it in Word and saving it again.")
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise HubError("That Word file couldn't be read safely.")
    root = ElementTree.fromstring(xml)
    blocks = []
    for paragraph in root.iter(WORD_NS + "p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == WORD_NS + "t":
                parts.append(node.text or "")
            elif node.tag == WORD_NS + "tab":
                parts.append("    ")
            elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
                parts.append("\n")
        style = paragraph.find(WORD_NS + "pPr/" + WORD_NS + "pStyle")
        heading = style is not None and str(style.get(WORD_NS + "val", "")).lower().startswith(("heading", "title"))
        text = "".join(parts)
        if not text.strip():
            blocks.append(("blank", ""))
            continue
        for line in text.split("\n"):
            blocks.append(("h" if heading else "p", line.strip()))
    return blocks


def blocks_of(path):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return docx_blocks(path)
    if suffix in TEXT_TYPES:
        return text_blocks(path.read_text(encoding="utf-8"), suffix == ".md")
    raise HubError("The hub can't turn a PDF into a Word file. Tip: Word can open a PDF directly (File → Open).")


def make_docx(blocks):
    """A simple Word file: one paragraph per block, in Calibri 11."""
    def run(text, bold=False, size=22):
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        props = ('<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
                 + ("<w:b/>" if bold else "") + '<w:sz w:val="' + str(size) + '"/></w:rPr>')
        return "<w:r>" + props + '<w:t xml:space="preserve">' + xml_escape(clean) + "</w:t></w:r>"

    paragraphs = []
    for kind, text in blocks:
        spacing = '<w:pPr><w:spacing w:after="0"/></w:pPr>'
        if kind == "h":
            paragraphs.append("<w:p>" + spacing + run(text, bold=True, size=28) + "</w:p>")
        elif kind == "p":
            paragraphs.append("<w:p>" + spacing + run(text) + "</w:p>")
        else:
            paragraphs.append("<w:p>" + spacing + "</w:p>")
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                + "".join(paragraphs)
                + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" '
                  'w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
                  "</w:body></w:document>")
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
                     'officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", rels)
        package.writestr("word/document.xml", document)
    return buffer.getvalue()


# Helvetica letter widths (in 1/1000 of the font size) for characters 32 to 126, for wrapping lines.
HELVETICA = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
             556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
             1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
             667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
             333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
             556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]


def text_width(text, size, bold):
    total = sum(HELVETICA[ord(c) - 32] if 32 <= ord(c) <= 126 else 600 for c in text)
    return total * size / 1000 * (1.08 if bold else 1.0)


def wrap(text, size, bold, width):
    lines, line = [], ""
    for word in text.split(" "):
        test = (line + " " + word) if line else word
        if line and text_width(test, size, bold) > width:
            lines.append(line)
            line = word
        else:
            line = test
    lines.append(line)
    return lines


def pdf_string(text):
    raw = text.encode("cp1252", errors="replace")
    return b"(" + raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def make_pdf(blocks):
    """A simple letter-size PDF with one-inch margins."""
    page_w, page_h, margin = 612, 792, 72
    usable = page_w - 2 * margin
    pages, current, y = [], [], page_h - margin
    for kind, text in blocks:
        bold = kind == "h"
        size = 14 if bold else 11
        leading = size * 1.4
        lines = wrap(text, size, bold, usable) if kind != "blank" else [""]
        for line in lines:
            if y - leading < margin:
                pages.append(current)
                current, y = [], page_h - margin
            y -= leading
            if line:
                font = b"/F2" if bold else b"/F1"
                current.append(b"BT " + font + b" " + str(size).encode() + b" Tf "
                               + str(margin).encode() + b" " + ("%.1f" % y).encode() + b" Td "
                               + pdf_string(line) + b" Tj ET")
    pages.append(current)

    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for page in pages:
        stream = b"\n".join(page)
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        content_number = len(objects)
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       b"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents "
                       + str(content_number).encode() + b" 0 R >>")
        kids.append(str(len(objects)).encode() + b" 0 R")
    objects[1] = b"<< /Type /Pages /Kids [" + b" ".join(kids) + b"] /Count " + str(len(kids)).encode() + b" >>"

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n")
    for offset in offsets:
        out.write(("%010d 00000 n \n" % offset).encode())
    out.write(b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\nstartxref\n"
              + str(xref).encode() + b"\n%%EOF\n")
    return out.getvalue()


def download_copy(query):
    """The file to download, as (bytes, file name, content type), in the format asked for."""
    path = document_path(query)
    want = (query.get("as") or [""])[0]
    suffix = path.suffix.lower()
    if want not in ("pdf", "docx"):
        raise HubError("Choose Word or PDF.")
    if suffix == "." + want:
        return path.read_bytes(), path.name, FILE_TYPES[suffix]
    blocks = blocks_of(path)
    data = make_pdf(blocks) if want == "pdf" else make_docx(blocks)
    return data, path.stem + "." + want, FILE_TYPES["." + want]


def safe_file_name(name):
    """Keep only letters, numbers, spaces, dashes, dots, and underscores in an uploaded file's name."""
    name = name.replace("\\", "/").split("/")[-1]
    stem = re.sub(r"[^A-Za-z0-9 ._-]+", "", Path(name).stem).strip(" .")[:80]
    return (stem or "file") + Path(name).suffix.lower()


def post_upload(body):
    folder = body.get("folder")
    if folder not in UPLOAD_FOLDERS:
        raise HubError("Choose where to keep the file: résumés, cover letters, or other files.")
    name = safe_file_name(str(body.get("name") or ""))
    suffix = Path(name).suffix
    if suffix not in KINDS:
        raise HubError("The hub can keep PDF (.pdf), Word (.docx), and text (.txt, .md) files.")
    try:
        data = base64.b64decode(str(body.get("data") or ""), validate=True)
    except ValueError:
        raise HubError("The hub couldn't read that file. Try choosing it again.")
    if not data:
        raise HubError("That file is empty.")
    if len(data) > MAX_UPLOAD:
        raise HubError("That file is bigger than 10 MB. Try a smaller copy.", 413)
    # Check the file really is what its name says.
    if suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise HubError("That file is named .pdf but isn't a PDF.")
    if suffix == ".docx" and not data.startswith(b"PK\x03\x04"):
        raise HubError("That file is named .docx but isn't a Word file. (Old .doc files: save them as .docx first.)")
    if suffix in TEXT_TYPES:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise HubError("That text file couldn't be read. Save it as plain text (UTF-8) and try again.")
    with SAVE_LOCK:
        base = FOLDERS[folder]
        base.mkdir(parents=True, exist_ok=True)
        path = base / name
        number = 2
        while path.exists():  # never replace a file you already have
            path = base / (Path(name).stem + "-" + str(number) + suffix)
            number += 1
        temp = path.with_name("." + path.name + ".tmp")
        temp.write_bytes(data)
        os.replace(temp, path)
    return {"saved": path.name, "documents": list_documents()}


def post_check(body):
    job_id = body.get("id")
    if not isinstance(job_id, int) or isinstance(job_id, bool):
        raise HubError("Which job? The id should be a number.")
    note = body.get("note", "")
    if not isinstance(note, str):
        raise HubError("The note should be text.")
    with SAVE_LOCK:
        top = load_top10()
        for job in top.get("jobs", []):
            if job.get("id") == job_id:
                job["student_check"] = {
                    "checked": bool(body.get("checked")),
                    "agree": bool(body.get("agree", True)),
                    "note": note.strip()[:5000],
                }
                write_json(DATA / "top10.json", top)
                return {"saved": True, "student_check": job["student_check"]}
    raise HubError("Can't find that job in your top 10. Try reloading the page.", 404)


def post_tracker_add(body):
    job_id = body.get("id")
    with SAVE_LOCK:
        top = load_top10()
        if job_id not in top.get("top10", []):
            raise HubError("Can't find that job in your top 10. Try reloading the page.", 404)
        job = next(j for j in top["jobs"] if j.get("id") == job_id)
        rows = load_tracker()
        new = {col: "" for col in COLUMNS}
        new.update({
            "Company": job.get("employer", ""),
            "Role": job.get("title", ""),
            "Link": job.get("link", ""),
            "QUICK HIRE": "Yes" if job.get("quick_hire") else "",
            "Status": "Interested",
        })
        already = any(
            (new["Link"] and row["Link"] == new["Link"] and row["Role"] == new["Role"])
            or (row["Company"] == new["Company"] and row["Role"] == new["Role"])
            for row in rows
        )
        if not already:
            rows.append(new)
            save_tracker(rows)
    return {"tracker": rows, "added": not already}


def post_tracker(body):
    rows = clean_rows(body.get("rows"))
    with SAVE_LOCK:
        save_tracker(rows)
    return {"tracker": rows}


# ---------- interview practice ----------
# The coach is imported only inside these requests, so the Jobs page keeps working
# even if something is wrong with the coach.

def coach():
    """Load agents/interview_coach.py (and its helpers in agents/common.py)."""
    import sys
    agents = str(REPO / "agents")
    if agents not in sys.path:
        sys.path.insert(0, agents)
    try:
        import interview_coach
    except Exception as err:
        raise HubError("The interview coach couldn't start (" + type(err).__name__
                       + "). Check the hub's terminal window.", 500)
    return interview_coach


def ask_coach(work):
    """Run a coach request and turn its problems into plain-language errors."""
    try:
        return work()
    except HubError:
        raise
    except Exception as err:
        if type(err).__name__ == "AgentError":  # a problem the coach already explained
            raise HubError(str(err), 502)
        raise


def job_for(value):
    """The job from my top 10 (by id), or None for general practice."""
    if value in (None, "", "general"):
        return None
    if isinstance(value, dict):
        value = value.get("id")
    try:
        job_id = int(value)
    except (TypeError, ValueError):
        raise HubError("Which job? Pick one from your top 10, or General practice.")
    for job in load_top10().get("jobs", []):
        if job.get("id") == job_id:
            return job
    raise HubError("Can't find that job in your top 10. Try reloading the page.", 404)


def text_field(body, name, limit):
    value = body.get(name, "")
    if not isinstance(value, str):
        raise HubError("The " + name + " should be text.")
    return value.strip()[:limit]


def post_interview_question(body):
    job = job_for(body.get("job"))
    asked = body.get("asked") or []
    if not isinstance(asked, list) or not all(isinstance(q, str) for q in asked):
        raise HubError("The questions already asked should be a list of text.")
    asked = [q[:500] for q in asked[:12]]
    module = coach()
    return {"question": ask_coach(lambda: module.next_question(job, asked))}


def post_interview_feedback(body):
    job = job_for(body.get("job"))
    question = text_field(body, "question", 1000)
    answer = text_field(body, "answer", 8000)
    if not question:
        raise HubError("Which question are you answering? Try getting the question again.")
    if len(answer) < 15:
        raise HubError("Your answer is a little short. Try again and tell the whole story: "
                       "what happened, what you did, and how it turned out.")
    module = coach()
    return {"feedback": ask_coach(lambda: module.star_feedback(job, question, answer))}


def post_interview_save(body):
    job_title = text_field(body, "job_title", 200) or "General practice"
    answers = body.get("answers")
    if not isinstance(answers, list) or not answers:
        raise HubError("Answer at least one question before you save.")
    if len(answers) > 12:
        raise HubError("That's more answers than one practice session can hold.")
    for item in answers:
        if not isinstance(item, dict) or not isinstance(item.get("question"), str) \
                or not isinstance(item.get("answer"), str) or not isinstance(item.get("feedback"), dict):
            raise HubError("Each saved answer needs its question, your answer, and the feedback.")
        score = item["feedback"].get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            raise HubError("Each saved answer needs a STAR score from 1 to 5.")
    from datetime import date
    today = date.today().isoformat()
    session = {"date": today, "job": job_title, "answers": answers}
    folder = DATA / "interviews"
    with SAVE_LOCK:
        folder.mkdir(parents=True, exist_ok=True)
        number = 1
        while (folder / ("%s-%02d.json" % (today, number))).exists():
            number += 1
        path = folder / ("%s-%02d.json" % (today, number))
        write_json(path, session)
    return {"saved": path.name, "interviews": list_interviews()}


POST_ROUTES = {"/api/check": post_check, "/api/tracker/add": post_tracker_add, "/api/tracker": post_tracker,
               "/api/upload": post_upload,
               "/api/interview/question": post_interview_question,
               "/api/interview/feedback": post_interview_feedback,
               "/api/interview/save": post_interview_save}


class Hub(SimpleHTTPRequestHandler):
    """Serves site/ and answers /api/ requests."""

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def from_this_computer(self):
        host = (self.headers.get("Host") or "").lower()
        if host.startswith("["):
            return False
        return host.split(":")[0] in ("localhost", "127.0.0.1")

    def answer(self, work):
        try:
            if not self.from_this_computer():
                raise HubError("The hub only answers requests from this computer.", 403)
            self.send_json(work())
        except HubError as err:
            self.send_json({"error": str(err)}, err.status)
        except Exception as err:  # anything unexpected: explain, don't crash
            self.log_error("Unexpected problem: %r", err)
            self.send_json({"error": "Something went wrong in the hub. Check the hub's terminal window."}, 500)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/hub":
            self.answer(get_hub)
        elif url.path == "/api/document":
            self.answer(lambda: get_document(parse_qs(url.query)))
        elif url.path == "/api/file":
            self.send_document_file(parse_qs(url.query))
        elif url.path == "/api/download":
            self.send_download(parse_qs(url.query))
        elif url.path.startswith("/api/"):
            self.send_json({"error": "The hub doesn't have that page."}, 404)
        elif not SITE.is_dir():
            self.send_json({"error": "The site/ folder isn't built yet. Build the front end (Prompt 8)."}, 404)
        else:
            super().do_GET()

    def send_document_file(self, query):
        """Send a PDF or Word file: PDFs open in Chrome, Word files download."""
        try:
            if not self.from_this_computer():
                raise HubError("The hub only answers requests from this computer.", 403)
            path = document_path(query)
            suffix = path.suffix.lower()
            data = path.read_bytes()
        except HubError as err:
            self.send_json({"error": str(err)}, err.status)
            return
        content_type = FILE_TYPES.get(suffix, "text/plain; charset=utf-8")
        how = "inline" if suffix == ".pdf" else "attachment"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", how + "; filename*=UTF-8''" + quote(path.name))
        self.end_headers()
        self.wfile.write(data)

    def send_download(self, query):
        """Download a document as Word or PDF, making a copy in that format if needed."""
        try:
            if not self.from_this_computer():
                raise HubError("The hub only answers requests from this computer.", 403)
            data, name, content_type = download_copy(query)
        except HubError as err:
            self.send_json({"error": str(err)}, err.status)
            return
        except Exception as err:
            self.log_error("Unexpected problem: %r", err)
            self.send_json({"error": "Something went wrong making that copy."}, 500)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
        self.end_headers()
        self.wfile.write(data)

    def do_HEAD(self):
        self.send_error(405)

    def do_POST(self):
        def work():
            route = POST_ROUTES.get(urlparse(self.path).path)
            if route is None:
                raise HubError("The hub doesn't have that page.", 404)
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                raise HubError("The hub only accepts JSON.", 415)
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise HubError("The request was the wrong size.")
            limit = MAX_UPLOAD * 4 // 3 + MAX_BODY if route is post_upload else MAX_BODY
            if length <= 0 or length > limit:
                raise HubError("The request was empty or too big.", 413)
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise HubError("The hub couldn't read that request.")
            if not isinstance(body, dict):
                raise HubError("The hub couldn't read that request.")
            return route(body)
        self.answer(work)

    def list_directory(self, path):
        # Never show a list of files; only the pages themselves.
        self.send_error(404)
        return None


def main():
    handler = partial(Hub, directory=str(SITE))
    try:
        server = ThreadingHTTPServer((HOST, PORT), handler)
    except OSError:
        raise SystemExit("Port 8000 is already in use. Is the hub already running in another window?")
    print("Open http://localhost:8000 in Chrome")
    print("(Press Ctrl+C to stop the hub.)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nHub stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

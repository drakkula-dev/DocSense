# Backend Learning Notes — Document Upload API

Concepts, patterns, and gotchas learned while building the `/documents` upload
route and `document_service.py`. Written to review and actually understand
*why*, not just *what*.

---

## 1. Architecture: Route vs. Service Separation

**The core idea:** the route handles HTTP, the service handles business logic.
Never mix the two.

- **Route's job:** receive the request, pull out plain data, call the service,
  catch errors, return a response. Nothing more.
- **Service's job:** do the actual work (validate, extract, process). It
  should have zero knowledge that HTTP even exists.

**Why bother?**
- The service becomes testable without faking a whole HTTP request.
- The service becomes reusable — same function callable from a CLI script,
  a background worker, another route, etc.
- Bugs are easier to isolate: "is this an HTTP problem or a logic problem?"
  becomes obvious from which file the code lives in.

**The dependency only flows one way:**
Route → imports from → Service.
Service must **never** import from the route file, and should never import
FastAPI-specific things (`UploadFile`, `Request`, `HTTPException`) at all.
If your service file needs FastAPI to run, the separation isn't real yet.

**Test for "is this actually separated?"**
Could you copy `document_service.py` into a plain Python script (no FastAPI
installed) and call `process_document()` with some bytes? If yes — properly
separated.

---

## 2. FastAPI Concepts

### `UploadFile`
- It's an **object/wrapper**, not raw bytes.
- Gives you: `.filename` (string, client-supplied, unverified), `.content_type`
  (string, client-supplied, unverified), and access to the actual bytes via
  `.read()` (async) or `.file.read()` (sync).
- FastAPI does **not** validate file type, size, or corruption for you.
  It will accept literally any file, of any type — validation is 100% on you.
- There is no meaningful filesystem "path" involved. FastAPI may spool large
  uploads to a temp file internally for memory efficiency, but that's an
  implementation detail — you never get a real, usable path from it.

### Getting bytes out of `UploadFile`
Two ways, pick one per route:
```python
contents = await file.read()      # async method, route must be `async def`
contents = file.file.read()       # sync method, route can be a normal `def`
```
Either way, **this conversion has to happen before calling the service** —
the service should only ever receive plain `bytes`, never the `UploadFile`
object itself.

### `File()` vs `Form()`
Both read from `multipart/form-data` request bodies (the format used for
file uploads, which can carry regular fields *and* files together).
- `File()` → pulls out file content (often implicit when you type-hint
  `UploadFile`).
- `Form()` → pulls out regular text fields sent alongside the file (e.g. a
  `"description"` field the user typed in).

### Automatic validation FastAPI already does
If a file parameter is required (no default value) and the client submits
the request with no file attached at all, FastAPI/Starlette rejects it with
a `422` **before your route function even runs**. You don't need to write
code for this case.

### Where the "Choose File" dialog comes from
It's a **browser** feature (standard HTML file input), not FastAPI. By the
time your server-side code runs, the file has already been picked client-side
— your server only ever receives bytes + filename string + content-type
string. It never has access to, or knowledge of, where the file lived on the
user's computer.

---

## 3. `raise` vs `return` — the most important Python distinction here

| | `return` | `raise` |
|---|---|---|
| What it does | Ends the *current function*, hands back a value | Ends the *current function* AND immediately jumps to the nearest matching `except`, skipping everything in between |
| Can it be silently ignored? | Yes — caller must remember to check the value | No — it either gets caught explicitly, or propagates loudly (visible error, not a silent bad value) |
| Good for | Normal success results | Signaling failure |

**Rule of thumb used throughout this project:** any time `process_document`
determines something is wrong (wrong file type, empty file, too large,
extraction failed), it should **raise a custom exception** — never `return`
`None`/a string/a dict pretending to be an error. A returned "error message"
looks like a valid result to any caller that doesn't explicitly check for it,
which risks silently sending a `200 OK` for a failed operation.

`raise` does **not** crash "the whole program" — only the current function
stops, and control jumps to whatever catches it. If nothing catches it,
FastAPI itself will turn it into a generic `500` response rather than
literally crashing the server process.

---

## 4. Custom Exceptions

Define your own exception classes instead of reusing generic built-ins like
`ValueError`.

```python
class UnsupportedFileType(Exception):
    pass
```

**Why not just use `ValueError`?**
`ValueError` is too generic — if you `except ValueError:` in the route,
you'd accidentally catch *any* unrelated `ValueError` raised anywhere inside
the service (e.g. from a totally different bug), and mistakenly respond as
if it were an unsupported-file-type error. A custom exception class can only
ever mean the one specific thing you defined it for.

**Pattern used in this project:**
- `UnsupportedFileType` — file type identified, but not one you support.
- `UnidentifiedFileType` — file type couldn't be identified at all.
- (Planned) `EmptyFile`, `FileTooLarge`, `ExtractionFailed` — same pattern,
  one exception per distinct failure reason.

**In the route:** catch each specific exception and map it to the correct
HTTP status code. This mapping should live *only* in the route — the service
never mentions status codes.

```python
except UnsupportedFileType as e:
    raise HTTPException(status_code=415, detail=str(e))
```

---

## 5. The Three Layers Where an Upload Request Can Fail

1. **FastAPI itself** — file field missing entirely → automatic `422`,
   no code needed, your route never runs.
2. **The route** — the read step itself fails (dropped connection, I/O error
   during `file.read()`) → wrap the read in its own `try/except`. This is
   about *receiving* the file, unrelated to the file's contents.
3. **The service (`process_document`)** — file arrived fine, but its
   *content* is invalid (wrong type, empty, too large, extraction fails) →
   raises custom exceptions, which the route catches and maps to status
   codes.

---

## 6. File Type Validation

### Two layers of "what type is this file?"
1. **Claimed type** (cheap, unverified) — the `content_type` header or the
   filename's extension. Easy to get wrong or spoof; only useful as a quick
   first filter.
2. **Actual type** (authoritative) — determined by inspecting the real
   bytes. This is the check that actually matters.

### `filetype` library
- Detects file type by reading **magic bytes** (a signature at the start of
  the file), independent of filename or claimed content-type.
- Reliable for binary formats like **PDF** and **DOCX** (DOCX is internally
  a ZIP file with a specific structure — `filetype` handles that detection
  for you).
- **Cannot detect plain text.** There's no magic-byte signature for "text" —
  it's just bytes that happen to be readable. `filetype.guess()` returns
  `None` for text files, not `"txt"`.
- Install via `uv add filetype`.
- "Stub file not found" is just your **type checker** (mypy/Pyright)
  complaining the library has no type hints published — harmless, doesn't
  affect runtime. Safe to ignore or suppress per-import.

### Detecting text files (the fallback, since `filetype` can't)
Heuristic: try decoding the bytes as UTF-8. Success is treated as "probably
text."
```python
def is_txt_file(file: bytes) -> bool:
    try:
        file.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
```
**Important caveat:** this is a heuristic, not a guarantee. Some binary data
can coincidentally decode as valid UTF-8 (false positive). A stronger version
checks for null bytes first (`\x00` almost never appears in real text):
```python
def is_txt_file(file: bytes) -> bool:
    if b"\x00" in file:
        return False
    try:
        file.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
```

### `pathlib`
- For working with **file paths and filenames as strings** (e.g. pulling an
  extension off a filename: `Path(filename).suffix`).
- Does **not** inspect actual file content — it's reading a label, same
  trust level as the `content_type` header, not authoritative.
- Not useful here for anything beyond the cheap "claimed type" check, since
  there's no real filesystem path involved at this stage (the file only
  exists as in-memory bytes, never touches disk in this pipeline).

---

## 7. Data Structures: Set vs. List vs. Dict

Used for `ALLOWED_FILE_TYPES = {"pdf", "docx"}`.

- **Set** — correct choice here. Use when you only need fast "is this value
  in the collection?" checks, no key-value pairing, no meaningful order,
  no duplicates. Membership check is ~O(1) (hash-based).
- **List** — would technically work (`in` works on lists too), but
  membership check is O(n) (checks one by one), and using a list implies
  order/duplicates might matter, which they don't here.
- **Dict** — wrong tool unless you need to associate each item with some
  other value (a real key → value pairing). Forcing fake values just to use
  a dict is a sign it's the wrong structure.

`{"pdf", "docx"}` — curly braces with no colons — is set syntax. Curly
braces *with* colons (`{"pdf": ...}`) would make it a dict.

---

## 8. Code Comment Conventions Used

- `# NOTE:` — explains *what* a piece of code does or *why* it's written
  that way. Keep to one tight sentence, one line, when possible.
- `# TODO:` — marks planned/future work not yet implemented.
- If a comment can't be shortened to one line without losing meaning, that's
  often a sign the code itself might benefit from a clearer name instead of
  a longer comment.

---

## 9. Quick Reference: Response Status Codes Used

| Exception | Meaning | HTTP Status |
|---|---|---|
| (missing file field) | FastAPI auto-rejects | `422 Unprocessable Entity` |
| `UnsupportedFileType` | Recognized type, not allowed | `415 Unsupported Media Type` |
| `UnidentifiedFileType` | Can't tell what it is | `415 Unsupported Media Type` |
| `EmptyFile` (planned) | Zero-byte upload | `422 Unprocessable Entity` |
| `FileTooLarge` (planned) | Over size limit | `413 Payload Too Large` |
| `ExtractionFailed` (planned) | Valid type, extraction broke | `422 Unprocessable Entity` |
| Success | — | `201 Created` (this project uses 201 since a resource is created) |

---

## 10. Imports Covered So Far

| Import | From | What it's for |
|---|---|---|
| `Annotated` | `typing` (built-in) | Attaches extra metadata (like `File(...)`) to a type hint |
| `Any` | `typing` (built-in) | Generic "could be anything" type hint |
| `FastAPI` | `fastapi` | Creates the main application instance everything attaches to |
| `APIRouter` | `fastapi` | Groups related routes together |
| `UploadFile` | `fastapi` | Wrapper object representing an uploaded file |
| `File` | `fastapi` | Marks a parameter as coming from multipart file data |
| `status` | `fastapi` | Named HTTP status code constants (`status.HTTP_201_CREATED`) instead of magic numbers |
| `HTTPException` | `fastapi` | Raised in the route to return a specific HTTP error response |
| `filetype` | third-party (`uv add filetype`) | Detects real file type from magic bytes |

---

## 11. Composing the App — `main.py`

Once you have multiple routers (health, documents, etc.), `main.py` is where
they all get wired together into one running application.

```python
from fastapi import FastAPI

from .routes.health import router as health_router
from .routes.documents import router as file_router

app = FastAPI()

app.include_router(health_router)
app.include_router(file_router, prefix="/files")
```

- **`FastAPI()`** — creates the single application instance that represents
  your entire API. Everything else (routers, middleware, exception handlers)
  attaches to this one object.
- **`app.include_router(...)`** — registers a router's endpoints onto the
  app. This is *why* splitting routes into separate files per resource
  (`health.py`, `documents.py`, ...) works cleanly — each file defines its
  own routes independently, and `main.py` just assembles them. No route
  logic should live in `main.py` itself.
- **`prefix="/files"`** — prepends a path segment to *every* route defined
  in that router. The documents router defines its upload route as
  `@router.post("/")`, but because it's included with `prefix="/files"`,
  the real, live endpoint becomes `POST /files/`. This lets each router
  define routes relative to its own resource (just `"/"`, `"/{id}"`, etc.)
  without needing to know or repeat the full path itself.
- **Scales cleanly** — adding a new resource later (e.g. users, auth) means
  creating a new router file and adding one more `include_router()` line
  here, not touching existing routes.

---

## 13. HTTP Methods & REST Conventions (CRUD)

As routes expand beyond just uploading, each HTTP method maps to a
conventional meaning. FastAPI doesn't enforce any of this — it's a
convention you follow so your API behaves the way other developers expect.

| Method | Meaning | Typical use here | Success status |
|---|---|---|---|
| `POST` | Create something new | Upload a new document | `201 Created` |
| `GET` | Read/retrieve, no side effects | Fetch one document or list all | `200 OK` |
| `PUT` | **Replace** a resource entirely | Re-upload a document, overwriting it | `200 OK` |
| `PATCH` | Update **part** of a resource | Rename a document, re-trigger extraction | `200 OK` |
| `DELETE` | Remove a resource | Delete a document and its data | `204 No Content` (or `200`) |

**`PUT` vs `PATCH` — the distinction that trips people up:**
- `PUT` implies you're sending the *entire* resource and it should fully
  replace what's stored — anything you don't include is conceptually gone.
- `PATCH` implies you're sending only the *fields that changed*, and
  everything else stays as-is.

For this project: uploading a brand-new version of a file to replace an old
one → `PUT`. Just renaming a document or re-running extraction on the
existing file → `PATCH`. Many small APIs only implement `PATCH` and skip
`PUT` entirely if full replacement never really happens — that's a
legitimate, common choice, not a shortcut.

**Why none of GET/PUT/PATCH/DELETE can be built yet:**
All four require something to look up, replace, or delete — which means a
document needs to be **persisted** (saved to a database and/or file storage)
first. Right now `process_document` runs entirely in memory and returns a
result — nothing is saved anywhere yet. Persistence is the real prerequisite
behind all four of these routes, not the routes themselves.

---

## 14. Mental Model to Remember

```
Client uploads file
        │
        ▼
 FastAPI (auto-checks required field exists) ──► 422 if missing
        │
        ▼
   Route: await file.read()  ──► try/except for read failures
        │  (UploadFile → bytes)
        ▼
   Service: process_document(bytes, filename, content_type)
        │
        ├─ detect type (claimed hint + filetype magic-byte check)
        ├─ raise UnsupportedFileType / UnidentifiedFileType if bad
        ├─ (planned) check empty/size → raise EmptyFile / FileTooLarge
        ├─ (planned) extract content → raise ExtractionFailed if it breaks
        └─ return a plain result object
        │
        ▼
   Route: catch exceptions → map to HTTP status
          on success → return result as JSON
```

**The one rule that ties all of this together:** the service only ever deals
in plain Python data (bytes, strings, custom exceptions) — never HTTP
concepts. The route only ever deals in HTTP concerns — never business logic.
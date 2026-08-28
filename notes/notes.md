# DocSense — Learning Notes

> An AI Document Intelligence API for extracting, formatting, summarizing, and analyzing document content.
> Target users: HR managers, legal teams, researchers, anyone drowning in documents.

---

## 1. FastAPI Fundamentals

### 1.1 The App Instance

```python
from fastapi import FastAPI
app = FastAPI()
```

- **One app to rule them all.** Every router, middleware, and exception handler attaches to this single instance.
- FastAPI auto-generates OpenAPI docs at `/docs` (Swagger UI) and `/redoc`.

### 1.2 Routers (`APIRouter`)

```python
from fastapi import APIRouter
router = APIRouter()

@router.post("/")
def upload_file(...): ...
```

- Routers group related endpoints (e.g., all `/documents` routes).
- Keeps code modular — each domain gets its own file.
- Mount routers with prefixes in `main.py`:

  ```python
  app.include_router(file_router, prefix="/files")
  # Results in POST /files/
  ```

### 1.3 Status Codes

```python
from fastapi import status
@router.post("/", status_code=status.HTTP_201_CREATED)
```

- Always return semantically correct status codes.
- `201 Created` for successful resource creation.
- `200 OK` for reads, `204 No Content` for successful deletes.

### 1.4 File Uploads with `UploadFile`

```python
from fastapi import UploadFile, File
from typing import Annotated

@router.post("/")
def upload_file(
    file: Annotated[UploadFile, File(description="PDF, DOCX, TXT ONLY")]
) -> dict[Any, Any]:
    file_content = file.file.read()
```

- `Annotated[UploadFile, File(...)]` tells FastAPI to expect a **file upload**, not JSON.
- `UploadFile` is a wrapper around a SpooledTemporaryFile — memory-efficient for large files.
- `.file.read()` reads the uploaded file into raw `bytes`.
- **Important:** `UploadFile` also gives you `.filename`, `.content_type`, `.size` (after reading).

### 1.5 Type Hints with `Annotated`

```python
from typing import Annotated
```

- `Annotated` attaches metadata to types without changing the type itself.
- Used here to attach `File()` metadata to `UploadFile`.
- Makes the API schema self-documenting in `/docs`.

---

## 2. Python File Handling & Type Detection

### 2.1 Reading Files as Bytes

```python
file_content = file.file.read()  # Returns bytes
```

- Always process files as `bytes` first for type detection.
- Never trust the file extension from `filename` — it's user-controlled and easily spoofed.

### 2.2 Magic-Byte Detection with `filetype`

```python
import filetype
file_kind = filetype.guess(file_bytes)
```

- `filetype.guess()` identifies files by their **magic bytes** (file signatures), not their names.
- Returns an object with `.extension` and `.mime` if identified.
- Returns `None` if the file type is unknown.
- **Limitation:** Cannot detect plain text files (`.txt`) because they have no magic bytes.

### 2.3 Detecting Plain Text Files

```python
def is_txt_file(file: bytes) -> bool:
    try:
        file.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
```

- Plain text has no magic bytes, so we use a **UTF-8 decode test** as a heuristic.
- If it decodes cleanly, we treat it as text.
- **Caveat:** This is naive. A binary file could coincidentally be valid UTF-8. For production, consider also checking for control characters or using `chardet`.

### 2.4 Custom Exceptions for File Processing

```python
class UnsupportedFileType(Exception):
    pass

class UnidentifiedFileType(Exception):
    pass
```

- Define domain-specific exceptions for clean error handling.
- These will be caught by a **global exception handler** (TODO) and converted to HTTP responses.

---

## 3. Service Layer Architecture

### 3.1 Separation of Concerns

```
routes/          # HTTP layer — parsing requests, returning responses
services/        # Business logic — file processing, AI analysis
models/          # Pydantic models — request/response validation
repositories/    # Data access — DB queries, file storage
```

- Routes should be thin. Heavy lifting belongs in `services/`.
- `process_document()` in the service layer handles type checking and (soon) text extraction.

### 3.2 Why Not Trust the Extension?

```python
# BAD — trusting user input
file_type = filename.split(".")[-1]

# GOOD — inspecting actual bytes
file_kind = filetype.guess(file_bytes)
```

- A user can rename `virus.exe` to `resume.pdf`. The extension lies; bytes don't.

---

## 4. Document Processing Pipeline (Planned)

### 4.1 Current Flow

```
Client uploads file
    ↓
FastAPI receives UploadFile
    ↓
Read raw bytes
    ↓
Detect file type (magic bytes → fallback UTF-8 test)
    ↓
Validate against ALLOWED_FILE_TYPES
    ↓
Return {filename, file_type}
```

### 4.2 Target Flow (DocSense v1)

```
Client uploads file
    ↓
FastAPI receives UploadFile
    ↓
Read raw bytes
    ↓
Detect & validate file type
    ↓
Extract text content (PDF → pdfplumber/pymupdf, DOCX → python-docx, TXT → decode)
    ↓
Store original file + extracted text (DB / object storage)
    ↓
Return {id, filename, file_type, extracted_text_preview}
```

### 4.3 Target Flow (DocSense v2 — AI Analysis)

```
Extracted text
    ↓
Chunk text (if large) + embed
    ↓
AI analysis pipeline:
    • Summarization
    • Entity extraction (names, dates, amounts, clauses)
    • Insight generation ("This contract expires in 30 days")
    • Comparison ("Diff between v1 and v2 of this policy")
    ↓
Return structured insights + raw text
```

---

## 5. Text Extraction Strategies by File Type

| File Type | Library | Approach |
| ----------- | --------- | ---------- |
| **PDF** | `pymupdf` (fitz) or `pdfplumber` | Extract text per page; handle scanned PDFs with OCR (`pytesseract` + `pdf2image`) |
| **DOCX** | `python-docx` | Read paragraphs, tables, headers; preserve structure |
| **TXT** | Native | `bytes.decode("utf-8")` with fallback to `chardet` for encoding detection |
| **Images** | `pytesseract` + `Pillow` | OCR for text-in-images (receipts, scanned forms, screenshots) |

### 5.1 Handling Scanned PDFs

- Some PDFs are just images wrapped in a PDF container.
- Strategy: If `pymupdf` returns empty text, convert pages to images and run OCR.
- Libraries: `pdf2image` (poppler required) → `Pillow` → `pytesseract`.

---

## 6. AI Integration Architecture

### 6.1 Use Cases for DocSense

1. **Summarization** — "Give me a 3-bullet summary of this 20-page contract."
2. **Entity Extraction** — "Find all dates, dollar amounts, and party names."
3. **Compliance Check** — "Flag any clauses that don't match our standard template."
4. **Q&A** — "What is the termination clause in this document?"
5. **Comparison** — "What changed between offer letter v1 and v2?"
6. **Insight Generation** — "This employee's contract has unusual non-compete terms."

### 6.2 Implementation Patterns

```python
# Pattern 1: Direct LLM call
from openai import AsyncOpenAI
client = AsyncOpenAI()

async def analyze_document(text: str, query: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a document analysis assistant."},
            {"role": "user", "content": f"Document:
{text}

Query: {query}"}
        ]
    )
    return response.choices[0].message.content
```

```python
# Pattern 2: Structured output (Pydantic)
from pydantic import BaseModel

class ContractInsights(BaseModel):
    parties: list[str]
    effective_date: str
    key_clauses: list[str]
    risks: list[str]
    summary: str

# Use OpenAI's structured outputs or function calling
```

### 6.3 Chunking for Large Documents

- LLMs have context limits (e.g., 128k tokens for GPT-4o).
- For large documents, chunk text intelligently:
  - By page
  - By paragraph
  - By semantic similarity (embeddings)
- Use **RAG** (Retrieval-Augmented Generation) for very large docs: chunk → embed → store in vector DB → retrieve relevant chunks for the query.

---

## 7. Error Handling & Resilience

### 7.1 Global Exception Handler (TODO)

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(UnsupportedFileType)
async def unsupported_file_handler(request: Request, exc: UnsupportedFileType):
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={"error": "Unsupported file type", "detail": str(exc)}
    )

@app.exception_handler(UnidentifiedFileType)
async def unidentified_file_handler(request: Request, exc: UnidentifiedFileType):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Could not identify file type", "detail": str(exc)}
    )
```

- Catches unhandled service exceptions and returns clean, consistent error responses.
- Prevents generic 500s from leaking internal details.

### 7.2 Validation Errors

- FastAPI auto-validates Pydantic models and returns `422 Unprocessable Entity`.
- Custom validators can enforce business rules (e.g., max file size).

---

## 8. CORS & Security (TODO)

### 8.1 CORS Middleware

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # NOT "*" in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

- Add once the frontend origin is known.
- Never use `allow_origins=["*"]` with `allow_credentials=True` — security risk.

### 8.2 File Upload Security Checklist

- [ ] Validate file type by magic bytes (done)
- [ ] Enforce max file size (`Request` middleware or nginx)
- [ ] Scan for malware (ClamAV or cloud-native scanner)
- [ ] Store files outside web root (S3, local volume, not `/static`)
- [ ] Sanitize filenames before storage
- [ ] Rate limit uploads per user/IP

---

## 9. Data Persistence (TODO)

### 9.1 What to Store

| Field | Type | Purpose |
| ------- | ------ | --------- |
| `id` | UUID / auto-increment | Primary key |
| `filename` | str | Original name |
| `stored_path` | str | Path in storage (S3 key or local path) |
| `file_type` | str | Detected type (pdf, docx, txt) |
| `extracted_text` | text | Full extracted content |
| `metadata` | JSON | Page count, word count, author, etc. |
| `created_at` | datetime | Upload timestamp |
| `updated_at` | datetime | Last modified |

### 9.2 Storage Options

- **Local filesystem**: Simple, but not scalable.
- **AWS S3 / GCS / Azure Blob**: Scalable, durable, cheap. Use presigned URLs for downloads.
- **Database (BLOB)**: Avoid for large files. Fine for small metadata.

### 9.3 API Endpoints to Implement

```
POST   /files/              → Upload document
GET    /files/              → List all documents (paginated)
GET    /files/{id}          → Get document metadata + extracted text
PUT    /files/{id}          → Replace document (full re-upload)
PATCH  /files/{id}          → Update metadata (rename, re-extract)
DELETE /files/{id}          → Remove document + stored file
POST   /files/{id}/analyze  → Run AI analysis on document
GET    /files/{id}/insights → Retrieve cached AI insights
```

---

## 10. Async vs Sync

### 10.1 When to Use `async`

- **Use `async`** for I/O-bound operations: DB queries, HTTP calls to LLM APIs, file uploads to S3.
- **Use sync** for CPU-bound operations: PDF text extraction, image OCR, heavy string processing.
- FastAPI runs sync functions in a threadpool, so they don't block the event loop.

### 10.2 Example

```python
# Sync — CPU-bound text extraction
def process_document(file: bytes) -> str:
    # pdfplumber, python-docx, etc.
    return extracted_text

# Async — I/O-bound AI call
async def analyze_with_llm(text: str) -> str:
    response = await openai_client.chat.completions.create(...)
    return response.choices[0].message.content
```

---

## 11. Testing Strategy

### 11.1 Unit Tests

- Test `process_document()` with sample files of each type.
- Mock LLM calls in analysis tests (use `respx` or `pytest-httpx`).
- Test edge cases: empty files, corrupted files, files with wrong extensions.

### 11.2 Integration Tests

- Use `TestClient` from FastAPI to hit endpoints.
- Use `tmp_path` fixture for file operations.
- Spin up a test DB (SQLite in-memory or Testcontainers for Postgres).

```python
from fastapi.testclient import TestClient
client = TestClient(app)

def test_upload_pdf():
    with open("tests/fixtures/sample.pdf", "rb") as f:
        response = client.post("/files/", files={"file": ("sample.pdf", f, "application/pdf")})
    assert response.status_code == 201
    assert response.json()["File Type"] == "pdf"
```

---

## 12. Project Roadmap

### Phase 1 — Foundation (Current)

- [x] Basic FastAPI app with routers
- [x] File upload endpoint
- [x] File type detection by magic bytes
- [ ] Global exception handler
- [ ] CORS middleware
- [ ] Text extraction (PDF, DOCX, TXT)
- [ ] Persist documents (DB + storage)

### Phase 2 — Core API

- [ ] GET /files (paginated list)
- [ ] GET /files/{id} (retrieve document)
- [ ] DELETE /files/{id}
- [ ] PUT/PATCH /files/{id}
- [ ] File size limits and validation

### Phase 3 — AI Intelligence

- [ ] Integrate LLM (OpenAI / Anthropic / local model)
- [ ] Summarization endpoint
- [ ] Entity extraction endpoint
- [ ] Q&A endpoint (chat with document)
- [ ] Structured output (Pydantic schemas)

### Phase 4 — Advanced Features

- [ ] Image support (OCR for JPG/PNG)
- [ ] Document comparison (diff)
- [ ] Batch processing (upload multiple files)
- [ ] Webhook notifications on processing complete
- [ ] User authentication & API keys

---

## 13. Quick Reference Cheatsheet

```python
# FastAPI router with prefix
app.include_router(router, prefix="/files", tags=["documents"])

# Annotated file upload
file: Annotated[UploadFile, File(description="...")]

# Read uploaded file
content = await file.read()  # async version
content = file.file.read()   # sync version

# Custom exception → HTTP response
@app.exception_handler(MyException)
async def handler(req, exc):
    return JSONResponse(status_code=400, content={"error": str(exc)})

# Pydantic response model
class UploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    extracted_text: str | None = None
```

---

## 14. Resources & References

- **FastAPI Docs**: <https://fastapi.tiangolo.com/>
- **Pydantic**: <https://docs.pydantic.dev/>
- **`filetype`**: <https://github.com/h2non/filetype.py>
- **`pymupdf` (fitz)**: <https://pymupdf.readthedocs.io/>
- **`python-docx`**: <https://python-docx.readthedocs.io/>
- **`pytesseract`**: <https://github.com/madmaze/pytesseract>
- **OpenAI API**: <https://platform.openai.com/docs/>

---

*Last updated: 2026-08-27*
*Project: DocSense — AI Document Intelligence API*

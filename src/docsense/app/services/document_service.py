import filetype
from docx import Document
import io

# NOTE: Raised when the file type is identified but not supported.
class UnsupportedFileType(Exception):
    pass

# NOTE: Raised when the file type cannot be identified at all.
class UnidentifiedFileType(Exception):
    pass

# NOTE: File types DocSense accepts.
ALLOWED_FILE_TYPES = {"pdf", "docx", "txt"}


def is_txt_file(file: bytes) -> bool:
    # NOTE: A successful UTF-8 decode is treated as a signal the file is plain text.
    try:
        file.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


# TODO: Extract and return the file's text content, not just its type.
def check_file(file: bytes):
    # NOTE: filetype.guess() identifies the file from its actual bytes, not its name.
    file_kind = filetype.guess(file)

    if file_kind is not None:
        if file_kind.extension not in ALLOWED_FILE_TYPES:
            raise UnsupportedFileType("Invalid file type")
        return file_kind.extension

    elif is_txt_file(file):
        # NOTE: filetype.guess() can't detect plain text — no magic bytes to match.
        return "txt"

    else:
        raise UnidentifiedFileType("Can't identify file type")

def extract_docx(docx_file: bytes) -> str:
    document = Document(io.BytesIO(docx_file))
    content = [para.text for para in document.paragraphs]

    return '\n'.join(content)


def process_file(file: bytes):
    file_type = check_file(file)

    if file_type == "docx":
        text = extract_docx(file)
    else:
        return None

    return {"type": file_type, "content": text}
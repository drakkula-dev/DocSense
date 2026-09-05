import filetype
from docx import Document
import io
import pymupdf


# NOTE: Raised when we recognize the file type but don't support it (e.g. an .exe).
class UnsupportedFileType(Exception):
    pass


# NOTE: Raised when we can't figure out the file type at all.
class UnidentifiedFileType(Exception):
    pass


# NOTE: The only file types DocSense will process.
ALLOWED_FILE_TYPES = {"pdf", "docx", "txt"}


def is_txt_file(file: bytes) -> bool:
    # NOTE: Plain text has no "magic bytes" (a signature at the start of the
    # file that identifies its type), so filetype.guess() can't detect it.
    # We fall back to trying a UTF-8 decode: if it succeeds, we treat it as text.
    try:
        file.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def check_file(file: bytes):
    # NOTE: filetype.guess() reads the file's actual bytes to identify its type,
    # so it works even if the filename/extension is missing or wrong.
    file_kind = filetype.guess(file)

    if file_kind is not None:
        if file_kind.extension not in ALLOWED_FILE_TYPES:
            raise UnsupportedFileType("Invalid file type")
        return file_kind.extension

    elif is_txt_file(file):
        # NOTE: Only reached if filetype.guess() found no match, since it can't
        # detect plain text on its own.
        return "txt"

    else:
        raise UnidentifiedFileType("Can't identify file type")


def extract_docx(docx_file: bytes) -> str:
    # NOTE: python-docx only reads paragraph text; it won't pick up content in
    # tables, headers/footers, or images.
    document = Document(io.BytesIO(docx_file))
    content = [para.text for para in document.paragraphs]

    docx_text = "\n".join(content).strip()

    return docx_text


def extract_pdf(pdf_file: bytes):
    with pymupdf.open(stream=pdf_file, filetype="pdf") as document:
        pdf_text = []
        pdf_imgs = []

        for page_num, page in enumerate(document, start=1):
            for img_index, img in enumerate(page.get_images(), start=1):
                xref = img[0]
                base_img = document.extract_image(xref)
                img_bytes = base_img["image"]
                img_ext = base_img["ext"]
                img_path = f"page_{page_num}_image_{img_index}.{img_ext}"

                with open (img_path, "wb") as f:
                    f.write(img_bytes)

                pdf_imgs.append(img_path)
            pdf_text.append(page.get_text())

        pdf_text = "".join(pdf_text).strip()
            
        content = {"text": pdf_text, "images": pdf_imgs}

        return content


def extract_txt(txt_file: bytes) -> str:
    # NOTE: A .txt file has no structure to parse, so decoding the raw bytes
    # is the entire extraction step.
    return txt_file.decode("utf-8").strip()


def process_file(file: bytes):
    file_type = check_file(file)
    images = []

    if file_type == "docx":
        text = extract_docx(file)
    elif file_type == "pdf":
        result = extract_pdf(file)
        text = result["text"]
        images = result["images"]
    elif file_type == "txt":
        text = extract_txt(file)
    else:
        # NOTE: Should be unreachable — check_file() only ever returns a type
        # in ALLOWED_FILE_TYPES. This guards against that invariant breaking
        # if a new type is added there without a matching extractor here.
        raise UnsupportedFileType(f"No extractor implemented for: {file_type}")

    return {"type": file_type, "content": {"text": text, "images": images}}
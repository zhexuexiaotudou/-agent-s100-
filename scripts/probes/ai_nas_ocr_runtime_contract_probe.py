#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
from pathlib import Path

from ai_nas_common import DEFAULT_REPORT_ROOT, ensure_report_dir, iso_now, ocr_engine_status, safe_write_json, safe_write_text


TOOL_ID = "ai_nas_ocr_runtime_contract"


def module_status(module_names: list[str]) -> dict:
    status = {}
    for name in module_names:
        try:
            module = __import__(name)
            status[name] = {
                "importable": True,
                "version": str(getattr(module, "__version__", "")),
                "error": None,
            }
        except Exception as exc:
            status[name] = {
                "importable": False,
                "version": None,
                "error": f"{type(exc).__name__}:{exc}",
            }
    return status


def command_status(command: list[str]) -> dict:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return {
            "command": command,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[:500],
            "stderr": proc.stderr[:500],
        }
    except Exception as exc:
        return {
            "command": command,
            "ok": False,
            "error": f"{type(exc).__name__}:{exc}",
        }


def prepare_fixture(root: Path) -> dict:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    text_pdf = root / "text_layer_invoice.pdf"
    scanned_image = root / "scanned_invoice_image.png"
    text_pdf_status = {"created": False, "engine": None, "error": None}

    from PIL import Image, ImageDraw

    text = "Invoice receipt 2024 renovation payment amount 12000 CNY date 2024-04-15"
    if importlib.util.find_spec("fitz") is not None:
        try:
            import fitz

            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 120), text)
            doc.save(text_pdf)
            doc.close()
            text_pdf_status = {"created": True, "engine": "PyMuPDF", "error": None}
        except Exception as exc:
            text_pdf_status = {"created": False, "engine": "PyMuPDF", "error": f"{type(exc).__name__}:{exc}"}
    if not text_pdf_status["created"] and importlib.util.find_spec("reportlab") is not None:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(str(text_pdf), pagesize=letter)
            c.drawString(72, 720, text)
            c.save()
            text_pdf_status = {"created": True, "engine": "reportlab", "error": None}
        except Exception as exc:
            text_pdf_status = {"created": False, "engine": "reportlab", "error": f"{type(exc).__name__}:{exc}"}

    image = Image.new("RGB", (900, 420), (250, 250, 245))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 870, 390), outline=(20, 20, 20), width=3)
    draw.text((60, 180), "SCANNED INVOICE 2024 PAYMENT 12000 CNY", fill=(0, 0, 0))
    image.save(scanned_image)
    return {
        "fixture_root": str(root),
        "text_pdf": str(text_pdf),
        "text_pdf_status": text_pdf_status,
        "scanned_image": str(scanned_image),
    }


def pdf_text_smoke(path: Path) -> dict:
    if not path.exists():
        return {"ok": False, "engine": None, "error": "text PDF fixture was not created"}
    expected_terms = ["Invoice", "renovation", "12000", "2024-04-15"]
    try:
        import fitz

        doc = fitz.open(str(path))
        try:
            text = "\n".join(page.get_text("text") for page in doc)
        finally:
            doc.close()
        return {
            "ok": all(term in text for term in expected_terms),
            "engine": "PyMuPDF",
            "text_preview": text[:500],
            "expected_terms_present": {term: term in text for term in expected_terms},
        }
    except Exception as fitz_exc:
        fitz_error = f"{type(fitz_exc).__name__}:{fitz_exc}"
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return {
            "ok": all(term in text for term in expected_terms),
            "engine": "pypdf",
            "text_preview": text[:500],
            "expected_terms_present": {term: term in text for term in expected_terms},
            "fallback_from": {"engine": "PyMuPDF", "error": fitz_error},
        }
    except Exception as pypdf_exc:
        pypdf_error = f"{type(pypdf_exc).__name__}:{pypdf_exc}"
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        return {
            "ok": all(term in text for term in expected_terms),
            "engine": "pdfplumber",
            "text_preview": text[:500],
            "expected_terms_present": {term: term in text for term in expected_terms},
            "fallback_from": {
                "PyMuPDF": fitz_error,
                "pypdf": pypdf_error,
            },
        }
    except Exception as pdfplumber_exc:
        pdfplumber_error = f"{type(pdfplumber_exc).__name__}:{pdfplumber_exc}"
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        try:
            proc = subprocess.run(
                [pdftotext, str(path), "-"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            text = proc.stdout or ""
            return {
                "ok": proc.returncode == 0 and all(term in text for term in expected_terms),
                "engine": "pdftotext",
                "command": [pdftotext, str(path), "-"],
                "returncode": proc.returncode,
                "text_preview": text[:500],
                "stderr": proc.stderr[:500],
                "expected_terms_present": {term: term in text for term in expected_terms},
                "fallback_from": {
                    "PyMuPDF": fitz_error,
                    "pypdf": pypdf_error,
                    "pdfplumber": pdfplumber_error,
                },
            }
        except Exception as pdftotext_exc:
            pdftotext_error = f"{type(pdftotext_exc).__name__}:{pdftotext_exc}"
    else:
        pdftotext_error = "pdftotext CLI not found on PATH"
    return {
        "ok": False,
        "engine": "PyMuPDF/pypdf/pdfplumber/pdftotext",
        "error": (
            f"PyMuPDF:{fitz_error} | "
            f"pypdf:{pypdf_error} | "
            f"pdfplumber:{pdfplumber_error} | "
            f"pdftotext:{pdftotext_error}"
        ),
    }


def scanned_image_detection_smoke(path: Path) -> dict:
    try:
        from PIL import Image
        import cv2
        import numpy as np

        image = Image.open(path).convert("L")
        arr = np.array(image)
        edges = cv2.Canny(arr, 50, 150)
        edge_density = float((edges > 0).sum()) / float(edges.size)
        return {
            "ok": edge_density > 0.005,
            "engine": "PIL+OpenCV",
            "width": image.width,
            "height": image.height,
            "edge_density": round(edge_density, 6),
            "scan_like": edge_density > 0.005,
        }
    except Exception as exc:
        return {"ok": False, "engine": "PIL+OpenCV", "error": f"{type(exc).__name__}:{exc}"}


def ocr_smoke(path: Path, runtime: dict) -> dict:
    if not runtime.get("ocr_ready"):
        return {
            "ok": False,
            "status": "blocked_missing_ocr_engine",
            "error": "missing tesseract CLI",
        }
    expected_any = ["INVOICE", "PAYMENT", "12000", "2024"]
    if runtime.get("pytesseract_importable"):
        try:
            import pytesseract
            from PIL import Image, ImageOps

            with Image.open(path) as image:
                text = pytesseract.image_to_string(ImageOps.exif_transpose(image).convert("RGB"))
            return {
                "ok": any(term in text.upper() for term in expected_any),
                "status": "ocr_completed" if text.strip() else "ocr_completed_no_text",
                "engine": "pytesseract+tesseract",
                "text_preview": text[:500],
                "expected_terms_present": {term: term in text.upper() for term in expected_any},
            }
        except Exception as exc:
            python_error = f"{type(exc).__name__}:{exc}"
    else:
        python_error = "pytesseract not importable"
    try:
        tesseract = runtime.get("tesseract_cli") or shutil.which("tesseract")
        proc = subprocess.run([tesseract, str(path), "stdout"], capture_output=True, text=True, timeout=30)
        text = proc.stdout or ""
        return {
            "ok": proc.returncode == 0 and any(term in text.upper() for term in expected_any),
            "status": "ocr_completed" if text.strip() else "ocr_completed_no_text",
            "engine": "tesseract_cli",
            "returncode": proc.returncode,
            "text_preview": text[:500],
            "stderr": proc.stderr[:500],
            "expected_terms_present": {term: term in text.upper() for term in expected_any},
            "fallback_from": {"pytesseract": python_error},
        }
    except Exception as exc:
        return {"ok": False, "status": "ocr_failed", "engine": "tesseract_cli", "error": f"{type(exc).__name__}:{exc}", "fallback_from": {"pytesseract": python_error}}


def install_manifest(runtime: dict, modules: dict) -> dict:
    missing = []
    if not runtime.get("tesseract_cli"):
        missing.append("tesseract CLI")
    if not runtime.get("tesseract_cli") and not modules.get("pytesseract", {}).get("importable"):
        missing.append("pytesseract Python package (optional when tesseract CLI is available)")
    return {
        "missing_requirements": missing,
        "windows_operator_steps": [
            "Install Tesseract OCR locally and ensure tesseract.exe is on PATH.",
            "Optionally install pytesseract into the runtime Python environment; CLI-only OCR is acceptable when tesseract stdout smoke passes.",
            "Re-run ai_nas_ocr_runtime_contract and ai_nas_ocr_extract against a scanned fixture.",
        ],
        "linux_operator_steps": [
            "Install the tesseract-ocr package through the OS package manager.",
            "Optionally install pytesseract into the OpenClaw/S100P Python runtime; CLI-only OCR is acceptable when tesseract stdout smoke passes.",
            "Re-run ai_nas_ocr_runtime_contract before claiming production OCR readiness.",
        ],
        "acceptance_required": [
            "tesseract CLI discoverable",
            "pytesseract importable or tesseract CLI stdout OCR smoke passes",
            "scanned image OCR smoke returns text",
            "ocr_results table records completed/failed/blocked status explicitly",
            "no invented content when OCR is unavailable or empty",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI-NAS production OCR runtime contract and local smoke report.")
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--fixture-root", type=Path, default=None)
    args = parser.parse_args()

    run_dir = ensure_report_dir(args.report_root, "ocr_runtime_contract")
    fixture = prepare_fixture(args.fixture_root or (run_dir / "fixture"))
    runtime = ocr_engine_status()
    modules = module_status(["fitz", "pypdf", "pdfplumber", "reportlab", "PIL", "cv2", "numpy", "pytesseract", "easyocr", "paddleocr"])
    commands = {
        "tesseract_version": command_status(["tesseract", "--version"]) if runtime.get("tesseract_cli") else {"ok": False, "error": "tesseract CLI not found on PATH"},
        "pdftotext_version": command_status(["pdftotext", "-v"]) if shutil.which("pdftotext") else {"ok": False, "error": "pdftotext CLI not found on PATH"},
    }
    pdf_text = pdf_text_smoke(Path(fixture["text_pdf"]))
    scan_detection = scanned_image_detection_smoke(Path(fixture["scanned_image"]))
    ocr = ocr_smoke(Path(fixture["scanned_image"]), runtime)
    manifest = install_manifest(runtime, modules)
    production_ocr_ready = bool(runtime.get("ocr_ready") and ocr.get("ok") and pdf_text.get("ok") and scan_detection.get("ok"))
    blockers = []
    if not pdf_text.get("ok"):
        blockers.append("pdf_text_layer_smoke_failed")
    if not scan_detection.get("ok"):
        blockers.append("scanned_image_detection_smoke_failed")
    if not runtime.get("ocr_ready"):
        blockers.append("ocr_runtime_missing")
    elif not ocr.get("ok"):
        blockers.append("ocr_smoke_failed")

    payload = {
        "generated_at": iso_now(),
        "tool_id": TOOL_ID,
        "verdict": "ok_ai_nas_ocr_runtime_contract" if production_ocr_ready else "limited_ai_nas_ocr_runtime_contract",
        "production_ocr_ready": production_ocr_ready,
        "scope": "local OCR runtime contract for scanned PDFs/images in the AI-NAS document pipeline",
        "fixture": fixture,
        "runtime": runtime,
        "module_status": modules,
        "command_status": commands,
        "smoke": {
            "pdf_text_layer": pdf_text,
            "scanned_image_detection": scan_detection,
            "scanned_image_ocr": ocr,
        },
        "install_manifest": manifest,
        "summary": {
            "pdf_text_layer_ready": bool(pdf_text.get("ok")),
            "scan_detection_ready": bool(scan_detection.get("ok")),
            "ocr_runtime_ready": bool(runtime.get("ocr_ready")),
            "ocr_smoke_ok": bool(ocr.get("ok")),
            "production_ocr_ready": production_ocr_ready,
            "blockers": blockers,
        },
        "audit": {
            "source_files_modified": False,
            "personal_source_modified": False,
            "fixture_only": True,
            "download_performed": False,
            "network_call_performed": False,
            "service_started": False,
            "delete_performed": False,
            "move_performed": False,
            "overwrite_performed": False,
            "invent_content": False,
            "writes": "isolated PDF/image fixture plus Markdown/JSON OCR runtime contract report only",
        },
    }

    json_path = run_dir / "ocr_runtime_contract.json"
    md_path = run_dir / "ocr_runtime_contract.md"
    safe_write_json(json_path, payload)
    lines = [
        "# AI-NAS OCR Runtime Contract",
        "",
        f"- verdict: `{payload['verdict']}`",
        f"- production_ocr_ready: `{production_ocr_ready}`",
        f"- generated_at: `{payload['generated_at']}`",
        f"- pdf_text_layer_ready: `{payload['summary']['pdf_text_layer_ready']}`",
        f"- scan_detection_ready: `{payload['summary']['scan_detection_ready']}`",
        f"- ocr_runtime_ready: `{payload['summary']['ocr_runtime_ready']}`",
        f"- ocr_smoke_ok: `{payload['summary']['ocr_smoke_ok']}`",
        f"- blockers: `{blockers}`",
        "",
        "## Missing Requirements",
        "",
    ]
    if not manifest["missing_requirements"]:
        lines.append("- No OCR runtime requirement is missing.")
    for item in manifest["missing_requirements"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Acceptance Required", ""])
    for item in manifest["acceptance_required"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Audit", ""])
    for key, value in payload["audit"].items():
        lines.append(f"- {key}: `{value}`")
    safe_write_text(md_path, "\n".join(lines) + "\n")
    print(md_path)
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

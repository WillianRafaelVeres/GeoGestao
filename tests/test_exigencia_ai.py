import io
import json
import unittest
import zipfile
from unittest import mock

import fitz

import app


class ExigenciaAiTests(unittest.TestCase):
    def test_normalizes_numbered_items_without_losing_subitems(self):
        items = app._normalize_ai_items([
            {
                "codigo": "2.1",
                "titulo": "2.1 - Anuencia do confrontante 1",
                "resumo": "Assinar o documento.",
                "pagina": 2,
                "trecho_origem": "Anuencia do confrontante 1",
            },
            {
                "codigo": "2.2",
                "titulo": "Anuencia do confrontante 2",
                "resumo": "Assinar o documento.",
                "pagina": 2,
                "trecho_origem": "Anuencia do confrontante 2",
            },
        ])

        self.assertEqual([item["codigo"] for item in items], ["2.1", "2.2"])
        self.assertEqual(items[0]["titulo"], "Anuencia do confrontante 1")

    def test_extracts_text_from_pdf_and_uses_vision_for_scan(self):
        digital = fitz.open()
        page = digital.new_page()
        page.insert_text(
            (72, 72),
            "1 - Apresentar requerimento de retificacao assinado.\n"
            "2.1 - Anexar anuencia do confrontante Joao.\n"
            "2.2 - Anexar anuencia do confrontante Maria.",
        )
        digital_bytes = digital.tobytes()
        digital.close()

        digital_source = app._extract_ai_source(digital_bytes, "nota.pdf")
        self.assertEqual(digital_source["method"], "pdf_text")
        self.assertIn("2.2", digital_source["text"])

        scan = fitz.open()
        scan.new_page()
        scan_bytes = scan.tobytes()
        scan.close()
        scan_source = app._extract_ai_source(scan_bytes, "scan.pdf")
        self.assertEqual(scan_source["method"], "pdf_vision")
        self.assertTrue(scan_source["images"][0]["bytes"].startswith(b"\x89PNG"))

    def test_extracts_docx_without_external_converter(self):
        document_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body><w:p><w:r><w:t>1 - Corrigir memorial descritivo</w:t></w:r></w:p>'
            b'</w:body></w:document>'
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr("word/document.xml", document_xml)

        source = app._extract_ai_source(buffer.getvalue(), "nota.docx")
        self.assertEqual(source["method"], "docx_text")
        self.assertIn("Corrigir memorial", source["text"])

    def test_parses_structured_groq_response(self):
        response_body = {
            "items": [{
                "codigo": "3.1",
                "titulo": "Apresentar documento 1",
                "resumo": "Documento atualizado.",
                "pagina": 4,
                "trecho_origem": "apresentar documento",
            }]
        }
        fake_response = {
            "choices": [{"message": {"content": json.dumps(response_body)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
        with mock.patch.object(app, "_groq_post", return_value=fake_response):
            items, usage, compacted = app._groq_analyze_text(
                "[[PAGINA 4]]\n3.1 - Apresentar documento 1"
            )

        self.assertEqual(items[0]["codigo"], "3.1")
        self.assertEqual(usage["total_tokens"], 120)
        self.assertFalse(compacted)


if __name__ == "__main__":
    unittest.main()

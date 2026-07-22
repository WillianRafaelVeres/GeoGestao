import unittest

import app


class PrefeiturasConfigTests(unittest.TestCase):
    def test_parse_prefeitura_document_lines_removes_blanks_and_duplicates(self):
        documents = app.parse_prefeitura_document_lines(
            "\nMapa com proposta para retificacao\n\nMemorial descritivo\n"
            "Mapa com proposta para retificacao \n  ART assinada  \n"
        )

        self.assertEqual(
            documents,
            [
                "Mapa com proposta para retificacao",
                "Memorial descritivo",
                "ART assinada",
            ],
        )

    def test_parse_prefeitura_document_lines_preserves_numbered_items(self):
        documents = app.parse_prefeitura_document_lines(
            "1 - Requerimento\n2.1 - Documento do confrontante 1\n2.2 - Documento do confrontante 2"
        )

        self.assertEqual(documents[0], "1 - Requerimento")
        self.assertEqual(documents[1], "2.1 - Documento do confrontante 1")
        self.assertEqual(documents[2], "2.2 - Documento do confrontante 2")


if __name__ == "__main__":
    unittest.main()

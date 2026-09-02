import json
import unittest
from unittest import mock

import fitz

import app


class DespesaAiFieldNormalizationTests(unittest.TestCase):
    """Item 11 do pedido: a IA nunca decide sozinha -- tudo que nao valida vira
    null em vez de virar uma sugestao enganosa."""

    def test_valid_fields_pass_through(self):
        fields = app._normalize_despesa_ai_fields({
            "valor": 145.5,
            "data": "2026-09-02",
            "estabelecimento": "Cartorio de Registro de Imoveis",
            "cnpj": "12.345.678/0001-95",
            "descricao": "Emolumentos cartorarios",
            "categoria_sugerida": "taxa",
            "numero_documento": "1928",
        })
        self.assertEqual(fields["valor"], 145.5)
        self.assertEqual(fields["data"], "2026-09-02")
        self.assertEqual(fields["cnpj"], "12345678000195")
        self.assertEqual(fields["categoria_sugerida"], "TAXA")
        self.assertEqual(fields["numero_documento"], "1928")

    def test_zero_or_negative_value_becomes_none(self):
        fields = app._normalize_despesa_ai_fields({"valor": 0, "data": None, "estabelecimento": None,
                                                     "cnpj": None, "descricao": None,
                                                     "categoria_sugerida": None, "numero_documento": None})
        self.assertIsNone(fields["valor"])
        fields = app._normalize_despesa_ai_fields({"valor": -50, "data": None, "estabelecimento": None,
                                                     "cnpj": None, "descricao": None,
                                                     "categoria_sugerida": None, "numero_documento": None})
        self.assertIsNone(fields["valor"])

    def test_unparseable_date_becomes_none(self):
        fields = app._normalize_despesa_ai_fields({"valor": None, "data": "ontem", "estabelecimento": None,
                                                     "cnpj": None, "descricao": None,
                                                     "categoria_sugerida": None, "numero_documento": None})
        self.assertIsNone(fields["data"])

    def test_unknown_category_becomes_none(self):
        fields = app._normalize_despesa_ai_fields({"valor": None, "data": None, "estabelecimento": None,
                                                     "cnpj": None, "descricao": None,
                                                     "categoria_sugerida": "VIAGEM_ESPACIAL", "numero_documento": None})
        self.assertIsNone(fields["categoria_sugerida"])

    def test_cnpj_with_wrong_length_becomes_none(self):
        fields = app._normalize_despesa_ai_fields({"valor": None, "data": None, "estabelecimento": None,
                                                     "cnpj": "123", "descricao": None,
                                                     "categoria_sugerida": None, "numero_documento": None})
        self.assertIsNone(fields["cnpj"])

    def test_non_dict_input_returns_empty(self):
        self.assertEqual(app._normalize_despesa_ai_fields(None), {})
        self.assertEqual(app._normalize_despesa_ai_fields("nao e um dict"), {})


class MergeDespesaAiFieldsTests(unittest.TestCase):
    def test_first_non_empty_value_wins(self):
        target = {"valor": 100.0, "estabelecimento": None}
        app._merge_despesa_ai_fields(target, {"valor": 200.0, "estabelecimento": "Posto X", "data": None})
        # valor ja estava preenchido -- nao e sobrescrito por uma pagina seguinte.
        self.assertEqual(target["valor"], 100.0)
        # estabelecimento estava vazio -- passa a vir da segunda fonte.
        self.assertEqual(target["estabelecimento"], "Posto X")
        self.assertIsNone(target.get("data"))


class AnalyzeDespesaAttachmentTests(unittest.TestCase):
    """Item 10 do pedido: a leitura por IA devolve um rascunho de campos --
    nunca projeto, cliente, quem desembolsou ou qualquer decisao financeira."""

    def test_receipt_pdf_with_native_text_is_read_via_text_pass(self):
        digital = fitz.open()
        page = digital.new_page()
        page.insert_text(
            (72, 72),
            "Cartorio de Registro de Imoveis da Comarca\n"
            "Recibo de emolumentos cartorarios referente ao processo de retificacao\n"
            "Valor pago: R$ 145,00 - Data de emissao: 02/09/2026",
        )
        digital_bytes = digital.tobytes()
        digital.close()

        response_body = {
            "valor": 145.0, "data": "2026-09-02", "estabelecimento": "Cartorio de Registro de Imoveis",
            "cnpj": None, "descricao": "Emolumentos cartorarios", "categoria_sugerida": "TAXA",
            "numero_documento": None,
        }
        fake_response = {
            "choices": [{"message": {"content": json.dumps(response_body)}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 15, "total_tokens": 95},
        }
        with mock.patch.object(app, "_groq_post", return_value=fake_response):
            result = app.analyze_despesa_attachment(digital_bytes, "recibo.pdf")

        self.assertEqual(result["fields"]["valor"], 145.0)
        self.assertEqual(result["fields"]["categoria_sugerida"], "TAXA")
        self.assertEqual(result["source_method"], "pdf_text")
        # O rascunho so tem campos de comprovante -- nada de projeto/cliente/desembolsante.
        # (merge so grava a chave quando a fonte trouxe um valor nao-vazio.)
        allowed_keys = {"valor", "data", "estabelecimento", "cnpj", "descricao", "categoria_sugerida", "numero_documento"}
        self.assertTrue(set(result["fields"].keys()).issubset(allowed_keys))
        self.assertNotIn("projeto_id", result["fields"])
        self.assertNotIn("desembolsado_por", str(result["fields"]))

    def test_scanned_receipt_uses_vision_pass(self):
        scan = fitz.open()
        scan.new_page()
        scan_bytes = scan.tobytes()
        scan.close()

        response_body = {
            "valor": 50.0, "data": None, "estabelecimento": "Posto Ipiranga",
            "cnpj": None, "descricao": "Combustivel", "categoria_sugerida": "COMBUSTIVEL",
            "numero_documento": None,
        }
        fake_response = {
            "choices": [{"message": {"content": json.dumps(response_body)}}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220},
        }
        with mock.patch.object(app, "_groq_post", return_value=fake_response):
            result = app.analyze_despesa_attachment(scan_bytes, "foto_recibo.pdf")

        self.assertEqual(result["source_method"], "pdf_vision")
        self.assertEqual(result["fields"]["categoria_sugerida"], "COMBUSTIVEL")

    def test_no_identifiable_field_raises_instead_of_faking_data(self):
        digital = fitz.open()
        digital.new_page()
        digital_bytes = digital.tobytes()
        digital.close()
        # Pagina em branco tem texto vazio -> vai por vision; simula a IA nao achando nada.
        empty_response_body = {
            "valor": None, "data": None, "estabelecimento": None, "cnpj": None,
            "descricao": None, "categoria_sugerida": None, "numero_documento": None,
        }
        fake_response = {
            "choices": [{"message": {"content": json.dumps(empty_response_body)}}],
            "usage": {},
        }
        with mock.patch.object(app, "_groq_post", return_value=fake_response):
            with self.assertRaises(app.ExigenciaAIError):
                app.analyze_despesa_attachment(digital_bytes, "vazio.pdf")


if __name__ == "__main__":
    unittest.main()

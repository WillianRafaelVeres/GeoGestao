"""Testes de integracao das rotas HTTP do modulo de Despesas.

Diferente de tests/test_expense_service.py (que testa expense_service com o
repositorio mockado), este arquivo testa as ROTAS de app.py de ponta a ponta:
parsing de request.form/request.files, o que e encaminhado pro
expense_service, o conteudo das mensagens flash e o redirect final -- sem
precisar de login real (nao ha usuario de teste no ambiente) e sem tocar o
banco de producao.

Login e contornado via `view.__wrapped__`: login_required usa
`functools.wraps`, que preserva a funcao original em `__wrapped__`. Chamar
direto o `__wrapped__` pula so a checagem de sessao -- todo o resto da rota
(parsing, chamadas a expense_service/expense_repository, flash, redirect)
roda de verdade. `get_db()`, `expense_service` e `expense_repository` sao
mockados para nao depender de conexao nenhuma.
"""

import io
import unittest
from decimal import Decimal
from unittest import mock

import app as appmod
from flask import get_flashed_messages


class RouteTestCase(unittest.TestCase):
    def _run(self, view, path, form=None, user=None, **view_kwargs):
        ctx = appmod.app.test_request_context(path, method="POST", data=form or {})
        ctx.push()
        self.addCleanup(ctx.pop)
        appmod.g.user = user or {"id": 1, "nome": "Admin", "perfil_acesso": "admin"}
        response = view.__wrapped__(**view_kwargs)
        return response, get_flashed_messages(with_categories=True)


class CriarDespesaRouteTests(RouteTestCase):
    def test_valid_submission_calls_service_with_parsed_allocations(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "create_despesa") as create_mock, \
             mock.patch.object(appmod, "read_despesa_attachment", return_value=(None, None)):
            create_mock.return_value = {
                "id": 10, "descricao": "Matricula", "valor_total": Decimal("300.00"),
                "data_despesa": "2026-09-02",
            }
            response, flashes = self._run(
                appmod.financeiro_despesas_criar, "/financeiro/despesas",
                form={
                    "descricao": "Matricula", "valor_total": "300,00", "categoria": "MATRICULA",
                    "data_despesa": "2026-09-02", "desembolso_tipo": "EMPRESA",
                    "alocacao_projeto_id": ["245", "251"], "alocacao_valor": ["180,00", "120,00"],
                    "registro_uid": "abc-123",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/financeiro/despesas", response.location)
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs
        self.assertEqual(kwargs["descricao"], "Matricula")
        self.assertEqual(kwargs["valor_total"], 300.0)
        self.assertEqual(kwargs["desembolsado_por_tipo"], "EMPRESA")
        self.assertEqual(kwargs["alocacoes"], [
            {"projeto_id": 245, "valor": 180.0},
            {"projeto_id": 251, "valor": 120.0},
        ])
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))

    def test_missing_allocation_rejected_before_calling_service(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "create_despesa") as create_mock:
            response, flashes = self._run(
                appmod.financeiro_despesas_criar, "/financeiro/despesas",
                form={"descricao": "Matricula", "valor_total": "300,00", "desembolso_tipo": "EMPRESA"},
            )

        self.assertEqual(response.status_code, 302)
        create_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))

    def test_service_error_is_flashed_and_does_not_crash(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "create_despesa",
                                side_effect=appmod.expense_service.ExpenseServiceError("Soma nao bate.")):
            response, flashes = self._run(
                appmod.financeiro_despesas_criar, "/financeiro/despesas",
                form={
                    "descricao": "Matricula", "valor_total": "300,00", "desembolso_tipo": "EMPRESA",
                    "alocacao_projeto_id": ["245"], "alocacao_valor": ["100,00"],
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn(("danger", "Soma nao bate."), flashes)

    def test_non_manager_cannot_create_despesa(self):
        with mock.patch.object(appmod.expense_service, "create_despesa") as create_mock:
            response, flashes = self._run(
                appmod.financeiro_despesas_criar, "/financeiro/despesas",
                form={"descricao": "Matricula", "valor_total": "300,00"},
                user={"id": 2, "nome": "Tecnico", "perfil_acesso": "tecnico"},
            )
        self.assertEqual(response.status_code, 302)
        create_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))


class ClassificarDespesaRouteTests(RouteTestCase):
    def test_valid_submission_calls_classificar_despesa(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_repository, "get_ia_analysis", return_value=None), \
             mock.patch.object(appmod.expense_service, "classificar_despesa") as classificar_mock, \
             mock.patch.object(appmod, "read_despesa_attachment", return_value=(None, None)):
            classificar_mock.return_value = {
                "id": 7, "descricao": "recibo_1928", "valor_total": Decimal("145.00"),
                "data_despesa": "2026-09-02",
            }
            response, flashes = self._run(
                appmod.financeiro_despesas_classificar, "/financeiro/despesas/7/classificar",
                form={
                    "descricao": "recibo_1928", "valor_total": "145,00", "categoria": "TAXA",
                    "data_despesa": "2026-09-02", "desembolso_tipo": "PESSOA", "desembolsante_id": "9",
                    "alocacao_projeto_id": ["245"], "alocacao_valor": ["145,00"],
                },
                user={"id": 1, "nome": "Admin", "perfil_acesso": "admin"},
                despesa_id=7,
            )

        self.assertEqual(response.status_code, 302)
        classificar_mock.assert_called_once()
        kwargs = classificar_mock.call_args.kwargs
        self.assertEqual(kwargs["desembolsado_por_tipo"], "PESSOA")
        self.assertEqual(kwargs["desembolsante_id"], 9)
        self.assertEqual(kwargs["alocacoes"], [{"projeto_id": 245, "valor": 145.0}])
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))

    def test_open_ia_draft_is_marked_applied_after_classification(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_repository, "get_ia_analysis",
                                return_value={"id": 3, "status": "rascunho"}) as get_ia_mock, \
             mock.patch.object(appmod.expense_repository, "mark_ia_analysis_applied") as mark_mock, \
             mock.patch.object(appmod.expense_service, "classificar_despesa",
                                return_value={"id": 7, "descricao": "x", "valor_total": Decimal("10.00"), "data_despesa": "2026-09-02"}), \
             mock.patch.object(appmod, "read_despesa_attachment", return_value=(None, None)):
            self._run(
                appmod.financeiro_despesas_classificar, "/financeiro/despesas/7/classificar",
                form={
                    "descricao": "x", "valor_total": "10,00", "desembolso_tipo": "EMPRESA",
                    "alocacao_projeto_id": ["1"], "alocacao_valor": ["10,00"],
                },
                despesa_id=7,
            )
        get_ia_mock.assert_called_once()
        mark_mock.assert_called_once()


class ImportarDocumentosRouteTests(RouteTestCase):
    def test_multiple_files_create_one_draft_each(self):
        files = [
            (io.BytesIO(b"conteudo-1"), "recibo1.jpg"),
            (io.BytesIO(b"conteudo-2"), "recibo2.jpg"),
        ]
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_repository, "insert_lote", return_value=102), \
             mock.patch.object(appmod.expense_repository, "update_lote_total") as update_total_mock, \
             mock.patch.object(appmod, "read_despesa_attachment") as read_mock, \
             mock.patch.object(appmod.expense_service, "check_duplicate_anexo", return_value=None), \
             mock.patch.object(appmod, "dropbox_upload_despesa_attachment",
                                return_value=({"path": "/x", "name": "x.jpg"}, None)), \
             mock.patch.object(appmod.expense_service, "import_documento") as import_mock:
            read_mock.side_effect = [
                ({"bytes": b"1", "hash": "h1", "extension": ".jpg", "original_name": "recibo1.jpg", "size": 1}, None),
                ({"bytes": b"2", "hash": "h2", "extension": ".jpg", "original_name": "recibo2.jpg", "size": 1}, None),
            ]
            response, flashes = self._run(
                appmod.financeiro_despesas_importar, "/financeiro/despesas/importar",
                form={"arquivos": files},
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(import_mock.call_count, 2)
        update_total_mock.assert_called_once_with(mock.ANY, 102, 2)
        self.assertTrue(any("2 documento(s) importado(s)" in mensagem for _, mensagem in flashes))

    def test_duplicate_hash_is_skipped_not_imported(self):
        files = [(io.BytesIO(b"conteudo"), "recibo.jpg")]
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_repository, "insert_lote", return_value=103), \
             mock.patch.object(appmod.expense_repository, "update_lote_total"), \
             mock.patch.object(appmod, "read_despesa_attachment",
                                return_value=({"bytes": b"1", "hash": "h1", "extension": ".jpg",
                                                "original_name": "recibo.jpg", "size": 1}, None)), \
             mock.patch.object(appmod.expense_service, "check_duplicate_anexo",
                                return_value={"despesa_id": 55}), \
             mock.patch.object(appmod.expense_service, "import_documento") as import_mock:
            response, flashes = self._run(
                appmod.financeiro_despesas_importar, "/financeiro/despesas/importar",
                form={"arquivos": files},
            )

        import_mock.assert_not_called()
        self.assertTrue(any("ja existiam" in mensagem for _, mensagem in flashes))

    def test_no_files_is_rejected(self):
        with mock.patch.object(appmod.expense_repository, "insert_lote") as insert_lote_mock:
            response, flashes = self._run(
                appmod.financeiro_despesas_importar, "/financeiro/despesas/importar", form={},
            )
        insert_lote_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))


class RegistrarReembolsoRouteTests(RouteTestCase):
    def test_valid_submission_calls_service(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "registrar_reembolso") as registrar_mock, \
             mock.patch.object(appmod, "read_despesa_attachment", return_value=(None, None)):
            registrar_mock.return_value = {"id": 50, "valor": Decimal("300.00"), "despesas": [1, 2]}
            response, flashes = self._run(
                appmod.financeiro_reembolsos_criar, "/financeiro/reembolsos",
                form={"desembolsante_id": "7", "data_reembolso": "2026-09-02", "forma_reembolso": "PIX"},
                user={"id": 1, "nome": "Admin", "perfil_acesso": "admin"},
            )

        self.assertEqual(response.status_code, 302)
        registrar_mock.assert_called_once()
        self.assertEqual(registrar_mock.call_args.kwargs["desembolsante_id"], 7)
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))

    def test_only_admin_can_register_reembolso(self):
        # Item 18 do pedido: registrar reembolso e exclusivo de admin, mesmo
        # coordenador (que ja pode gerenciar despesas) fica de fora.
        with mock.patch.object(appmod.expense_service, "registrar_reembolso") as registrar_mock:
            response, flashes = self._run(
                appmod.financeiro_reembolsos_criar, "/financeiro/reembolsos",
                form={"desembolsante_id": "7"},
                user={"id": 3, "nome": "Coordenador", "perfil_acesso": "coordenador"},
            )
        registrar_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))


class CancelarReembolsoRouteTests(RouteTestCase):
    def test_cancel_calls_service_and_redirects(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "cancelar_reembolso") as cancelar_mock:
            response, flashes = self._run(
                appmod.financeiro_reembolsos_cancelar, "/financeiro/reembolsos/50/cancelar",
                form={"motivo": "Lancado errado"},
                reembolso_id=50,
            )
        self.assertEqual(response.status_code, 302)
        cancelar_mock.assert_called_once()
        self.assertEqual(cancelar_mock.call_args.args[1], 50)
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))


class CriarCobrancaRouteTests(RouteTestCase):
    def test_valid_submission_calls_service(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "criar_cobranca") as criar_mock:
            criar_mock.return_value = {"id": 900, "valor_total": Decimal("63.00")}
            response, flashes = self._run(
                appmod.financeiro_cobrancas_criar, "/financeiro/cobrancas",
                form={
                    "cliente_id": "7", "despesa_id": ["1", "2"],
                    "data_cobranca": "2026-09-02", "registro_uid": "abc-123",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/financeiro/cobrancas", response.location)
        criar_mock.assert_called_once()
        kwargs = criar_mock.call_args.kwargs
        self.assertEqual(kwargs["cliente_id"], 7)
        self.assertEqual(kwargs["despesa_ids"], [1, 2])
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))

    def test_missing_client_is_rejected_before_calling_service(self):
        with mock.patch.object(appmod.expense_service, "criar_cobranca") as criar_mock:
            response, flashes = self._run(
                appmod.financeiro_cobrancas_criar, "/financeiro/cobrancas",
                form={"despesa_id": ["1"]},
            )
        self.assertEqual(response.status_code, 302)
        criar_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))

    def test_service_error_is_flashed_and_does_not_crash(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "criar_cobranca",
                                side_effect=appmod.expense_service.ExpenseServiceError("Ja esta em outra cobranca.")):
            response, flashes = self._run(
                appmod.financeiro_cobrancas_criar, "/financeiro/cobrancas",
                form={"cliente_id": "7", "despesa_id": ["1"]},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn(("danger", "Ja esta em outra cobranca."), flashes)

    def test_non_manager_cannot_create_cobranca(self):
        with mock.patch.object(appmod.expense_service, "criar_cobranca") as criar_mock:
            response, flashes = self._run(
                appmod.financeiro_cobrancas_criar, "/financeiro/cobrancas",
                form={"cliente_id": "7", "despesa_id": ["1"]},
                user={"id": 2, "nome": "Tecnico", "perfil_acesso": "tecnico"},
            )
        self.assertEqual(response.status_code, 302)
        criar_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))


class CancelarCobrancaRouteTests(RouteTestCase):
    def test_cancel_calls_service_and_redirects(self):
        with mock.patch.object(appmod, "get_db", return_value=mock.Mock()), \
             mock.patch.object(appmod.expense_service, "cancelar_cobranca") as cancelar_mock:
            response, flashes = self._run(
                appmod.financeiro_cobrancas_cancelar, "/financeiro/cobrancas/900/cancelar",
                form={"motivo": "Lancado errado"},
                cobranca_id=900,
            )
        self.assertEqual(response.status_code, 302)
        cancelar_mock.assert_called_once()
        self.assertEqual(cancelar_mock.call_args.args[1], 900)
        self.assertTrue(any(categoria == "success" for categoria, _ in flashes))

    def test_non_manager_cannot_cancel_cobranca(self):
        with mock.patch.object(appmod.expense_service, "cancelar_cobranca") as cancelar_mock:
            response, flashes = self._run(
                appmod.financeiro_cobrancas_cancelar, "/financeiro/cobrancas/900/cancelar",
                form={}, cobranca_id=900,
                user={"id": 2, "nome": "Tecnico", "perfil_acesso": "tecnico"},
            )
        self.assertEqual(response.status_code, 302)
        cancelar_mock.assert_not_called()
        self.assertTrue(any(categoria == "danger" for categoria, _ in flashes))


if __name__ == "__main__":
    unittest.main()

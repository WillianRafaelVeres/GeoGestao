import unittest
from decimal import Decimal
from unittest import mock

import app as appmod
import expense_repository as repo
import expense_service as svc


class AllocationValidationTests(unittest.TestCase):
    """Item 4 do pedido: soma das alocacoes tem que bater com o total, sempre."""

    def test_single_project_matches_total(self):
        svc.validate_allocations_sum(300, [{"projeto_id": 1, "valor": 300}])  # nao deve levantar

    def test_two_projects_matching_total(self):
        svc.validate_allocations_sum(500, [
            {"projeto_id": 245, "valor": 300},
            {"projeto_id": 251, "valor": 200},
        ])  # nao deve levantar

    def test_sum_different_from_total_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.validate_allocations_sum(300, [
                {"projeto_id": 245, "valor": 180},
                {"projeto_id": 251, "valor": 100},
            ])

    def test_rounding_tolerance_of_one_cent_is_accepted(self):
        svc.validate_allocations_sum(Decimal("100.00"), [
            {"projeto_id": 1, "valor": Decimal("33.34")},
            {"projeto_id": 2, "valor": Decimal("33.33")},
            {"projeto_id": 3, "valor": Decimal("33.34")},
        ])  # soma 100.01, dentro da tolerancia de 1 centavo

    def test_no_allocations_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.validate_allocations_sum(100, [])

    def test_duplicate_project_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.validate_allocations_sum(200, [
                {"projeto_id": 1, "valor": 100},
                {"projeto_id": 1, "valor": 100},
            ])

    def test_zero_or_negative_allocation_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.validate_allocations_sum(100, [{"projeto_id": 1, "valor": 0}])


class SplitByPercentualTests(unittest.TestCase):
    def test_three_way_split_that_does_not_round_evenly_still_sums_to_total(self):
        # Caso classico: 33% + 33% + 34% (ou 33.33 recorrente) precisa fechar em centavos.
        result = svc.split_by_percentual(100, [(1, 33.33), (2, 33.33), (3, 33.34)])
        self.assertEqual(sum(result.values()), Decimal("100.00"))
        self.assertEqual(len(result), 3)

    def test_percentuals_not_summing_100_are_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.split_by_percentual(100, [(1, 50), (2, 30)])


class DisbursedByTests(unittest.TestCase):
    """Itens 5/6 do pedido: nunca confundir desembolso da empresa com desembolso de pessoa."""

    def test_company_disbursement_is_never_reimbursable(self):
        despesa = {"desembolsado_por_tipo": "EMPRESA", "desembolsado_por_id": None}
        self.assertFalse(svc.is_reembolsavel(despesa))

    def test_person_disbursement_is_reimbursable(self):
        despesa = {"desembolsado_por_tipo": "PESSOA", "desembolsado_por_id": 7}
        self.assertTrue(svc.is_reembolsavel(despesa))

    def test_status_becomes_pronta_only_with_allocations(self):
        self.assertEqual(svc.compute_despesa_status(has_alocacoes=False, has_desembolso=True), "classificada")
        self.assertEqual(svc.compute_despesa_status(has_alocacoes=True, has_desembolso=True), "pronta")


class ResolveDesembolsanteTests(unittest.TestCase):
    def test_empresa_never_creates_a_desembolsante_row(self):
        db = mock.Mock()
        result = svc.resolve_desembolsante(db, tipo="EMPRESA", criado_em="2026-09-02T10:00:00")
        self.assertIsNone(result)
        db.execute.assert_not_called()

    def test_pessoa_requires_a_name_or_existing_id(self):
        db = mock.Mock()
        with self.assertRaises(svc.ExpenseServiceError):
            svc.resolve_desembolsante(db, tipo="PESSOA", criado_em="2026-09-02T10:00:00")


class CreateDespesaTests(unittest.TestCase):
    """Item 1/2/4 do pedido, via camada de servico com o repositorio mockado."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.find_despesa_by_registro_uid.return_value = None

    def test_single_project_expense_is_ready_immediately(self):
        self.repo.insert_despesa.return_value = 1
        self.repo.get_despesa.return_value = {"id": 1, "status": "pronta"}
        self.repo.resolve_projeto_cliente.return_value = 42

        result = svc.create_despesa(
            self.db, descricao="Matricula atualizada", valor_total=300,
            desembolsado_por_tipo="EMPRESA", criado_em="2026-09-02T10:00:00",
            alocacoes=[{"projeto_id": 245, "valor": 300}],
        )

        self.assertEqual(result, {"id": 1, "status": "pronta"})
        self.repo.insert_despesa.assert_called_once()
        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["status"], "pronta")
        self.repo.insert_alocacao.assert_called_once_with(self.db, 1, 245, 42, Decimal("300.00"), "2026-09-02T10:00:00", percentual=None)

    def test_expense_split_across_projects_of_different_clients(self):
        # Item 4/5 do pedido: mesma despesa, dois projetos, dois clientes diferentes.
        self.repo.insert_despesa.return_value = 9
        self.repo.get_despesa.return_value = {"id": 9}
        self.repo.resolve_projeto_cliente.side_effect = lambda db, projeto_id: {245: 101, 251: 202}[projeto_id]

        svc.create_despesa(
            self.db, descricao="Matricula atualizada", valor_total=500,
            desembolsado_por_tipo="EMPRESA", criado_em="2026-09-02T10:00:00",
            alocacoes=[{"projeto_id": 245, "valor": 300}, {"projeto_id": 251, "valor": 200}],
        )

        calls = self.repo.insert_alocacao.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[:4], (self.db, 9, 245, 101))
        self.assertEqual(calls[1].args[:4], (self.db, 9, 251, 202))

    def test_allocation_sum_mismatch_prevents_any_write(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.create_despesa(
                self.db, descricao="Matricula", valor_total=300,
                desembolsado_por_tipo="EMPRESA", criado_em="2026-09-02T10:00:00",
                alocacoes=[{"projeto_id": 245, "valor": 180}, {"projeto_id": 251, "valor": 100}],
            )
        self.repo.insert_despesa.assert_not_called()

    def test_company_disbursement_resolves_to_no_desembolsante_id(self):
        self.repo.insert_despesa.return_value = 1
        self.repo.get_despesa.return_value = {"id": 1}
        self.repo.resolve_projeto_cliente.return_value = None

        svc.create_despesa(
            self.db, descricao="Taxa", valor_total=100,
            desembolsado_por_tipo="EMPRESA", criado_em="2026-09-02T10:00:00",
            alocacoes=[{"projeto_id": 1, "valor": 100}],
        )
        self.assertIsNone(self.repo.insert_despesa.call_args.kwargs["desembolsado_por_id"])

    def test_person_disbursement_resolves_desembolsante_id(self):
        self.repo.get_desembolsante.return_value = {"id": 7, "ativo": True}
        self.repo.insert_despesa.return_value = 1
        self.repo.get_despesa.return_value = {"id": 1}
        self.repo.resolve_projeto_cliente.return_value = None

        svc.create_despesa(
            self.db, descricao="Taxa", valor_total=100,
            desembolsado_por_tipo="PESSOA", desembolsante_id=7, criado_em="2026-09-02T10:00:00",
            alocacoes=[{"projeto_id": 1, "valor": 100}],
        )
        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["desembolsado_por_id"], 7)


class ImportDocumentoTests(unittest.TestCase):
    """Item 9 do pedido: cada arquivo importado vira um rascunho, nunca uma
    despesa pronta -- projeto, cliente e desembolsante ficam por definir."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)

    def test_imported_document_becomes_pending_draft_without_value(self):
        self.repo.insert_despesa.return_value = 55
        self.repo.get_despesa.return_value = {"id": 55, "status": "pendente_classificacao"}

        svc.import_documento(
            self.db, lote_id=3, descricao="recibo_1928",
            caminho_dropbox="/SC/Novo/_despesas/2026/09/recibo_1928.jpg",
            nome_arquivo="recibo_1928.jpg", nome_original="recibo_1928.jpg",
            file_hash="abc123", tamanho=1024, criado_em="2026-09-02T10:00:00", criado_por=1,
        )

        kwargs = self.repo.insert_despesa.call_args.kwargs
        self.assertIsNone(kwargs["valor_total"])
        self.assertEqual(kwargs["status"], "pendente_classificacao")
        self.assertEqual(kwargs["desembolsado_por_tipo"], "EMPRESA")
        self.assertEqual(kwargs["origem"], "IMPORTACAO")
        self.assertEqual(kwargs["lote_id"], 3)
        self.repo.insert_alocacao.assert_not_called()
        self.repo.insert_anexo.assert_called_once()


class ClassificarDespesaTests(unittest.TestCase):
    """Item 9/11 do pedido: so o usuario completa valor/projeto/desembolsante
    de um rascunho -- nunca a importacao sozinha."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.get_despesa.return_value = {
            "id": 1, "status": "pendente_classificacao", "desembolsado_por_tipo": "EMPRESA",
            "desembolsado_por_id": None,
        }

    def test_classifying_a_draft_completes_it_and_makes_it_ready(self):
        self.repo.resolve_projeto_cliente.return_value = 42

        svc.classificar_despesa(
            self.db, 1, descricao="Matricula atualizada", valor_total=300,
            categoria="MATRICULA", data_despesa="2026-09-02", observacoes=None,
            desembolsado_por_tipo="EMPRESA", alocacoes=[{"projeto_id": 245, "valor": 300}],
            atualizado_em="2026-09-02T11:00:00", atualizado_por=1,
        )

        self.repo.update_despesa_classificacao.assert_called_once()
        self.assertEqual(self.repo.update_despesa_classificacao.call_args.kwargs["valor_total"], Decimal("300.00"))
        self.repo.delete_alocacoes.assert_called_once_with(self.db, 1)
        self.repo.insert_alocacao.assert_called_once()
        self.repo.update_despesa_status.assert_called_once_with(self.db, 1, "pronta", "2026-09-02T11:00:00", 1)

    def test_missing_allocation_is_rejected_before_any_write(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.classificar_despesa(
                self.db, 1, descricao="Matricula", valor_total=300, categoria=None,
                data_despesa="2026-09-02", observacoes=None, desembolsado_por_tipo="EMPRESA",
                alocacoes=[], atualizado_em="2026-09-02T11:00:00",
            )
        # Nada pode ter sido escrito: um redirect de erro (302) nao e status
        # >=400, entao uma escrita parcial seria commitada mesmo assim.
        self.repo.update_despesa_classificacao.assert_not_called()
        self.repo.delete_alocacoes.assert_not_called()

    def test_allocation_sum_mismatch_is_rejected_before_any_write(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.classificar_despesa(
                self.db, 1, descricao="Matricula", valor_total=300, categoria=None,
                data_despesa="2026-09-02", observacoes=None, desembolsado_por_tipo="EMPRESA",
                alocacoes=[{"projeto_id": 1, "valor": 100}], atualizado_em="2026-09-02T11:00:00",
            )
        self.repo.update_despesa_classificacao.assert_not_called()

    def test_cannot_classify_cancelled_expense(self):
        self.repo.get_despesa.return_value = {"id": 1, "status": "cancelada"}
        with self.assertRaises(svc.ExpenseServiceError):
            svc.classificar_despesa(
                self.db, 1, descricao="Matricula", valor_total=300, categoria=None,
                data_despesa="2026-09-02", observacoes=None, desembolsado_por_tipo="EMPRESA",
                alocacoes=[{"projeto_id": 1, "valor": 300}], atualizado_em="2026-09-02T11:00:00",
            )


class CancelDespesaTests(unittest.TestCase):
    """Item 8 do pedido: cancelamento e soft, auditado, nunca DELETE."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)

    def test_cancel_active_expense(self):
        self.repo.get_despesa.return_value = {"id": 1, "status": "pronta", "descricao": "X", "valor_total": 100}
        self.repo.sum_reembolsado_por_despesa.return_value = 0.0

        svc.cancelar_despesa(self.db, 1, "Lancado por engano", "2026-09-02T10:00:00", cancelado_por=9)

        self.repo.cancel_despesa.assert_called_once_with(self.db, 1, "Lancado por engano", "2026-09-02T10:00:00", 9)
        self.repo.insert_evento.assert_called_once()

    def test_cannot_cancel_already_cancelled(self):
        self.repo.get_despesa.return_value = {"id": 1, "status": "cancelada"}
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_despesa(self.db, 1, None, "2026-09-02T10:00:00")
        self.repo.cancel_despesa.assert_not_called()

    def test_cancel_still_unclassified_expense_without_valor_total(self):
        # Regressao: descartar um documento da fila de Lancamentos (rascunho/
        # pendente_classificacao, sem valor_total ainda) precisa funcionar --
        # a constraint despesas_valor_total_check so permitia isso a partir da
        # migration fase9 (ver docs/FINANCEIRO_DESPESAS.md).
        self.repo.get_despesa.return_value = {
            "id": 1, "status": "pendente_classificacao", "descricao": "recibo.jpg", "valor_total": None,
        }
        self.repo.sum_reembolsado_por_despesa.return_value = 0.0

        svc.cancelar_despesa(self.db, 1, None, "2026-09-02T10:00:00", cancelado_por=9)

        self.repo.cancel_despesa.assert_called_once_with(self.db, 1, None, "2026-09-02T10:00:00", 9)
        self.repo.insert_evento.assert_called_once()

    def test_cannot_cancel_already_reimbursed_expense(self):
        self.repo.get_despesa.return_value = {"id": 1, "status": "pronta"}
        self.repo.sum_reembolsado_por_despesa.return_value = 300.0
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_despesa(self.db, 1, None, "2026-09-02T10:00:00")
        self.repo.cancel_despesa.assert_not_called()


class RegistrarReembolsoTests(unittest.TestCase):
    """Itens 6/7 do pedido: desembolso de pessoa gera saldo; reembolso encerra a obrigacao."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.find_reembolso_by_registro_uid.return_value = None
        self.repo.get_desembolsante.return_value = {"id": 7, "nome": "Rafael"}

    def test_reimburse_all_pending_expenses_of_a_person(self):
        self.repo.list_despesas_pendentes_por_desembolsante.return_value = [
            {"id": 1, "saldo_pendente": 180},
            {"id": 2, "saldo_pendente": 120},
        ]
        self.repo.insert_reembolso.return_value = 50

        result = svc.registrar_reembolso(
            self.db, desembolsante_id=7, data_reembolso="2026-09-02",
            criado_em="2026-09-02T10:00:00", criado_por=1,
        )

        self.assertEqual(result["valor"], Decimal("300.00"))
        self.repo.insert_reembolso.assert_called_once()
        self.assertEqual(self.repo.insert_reembolso.call_args.args[2], Decimal("300.00"))
        self.assertEqual(self.repo.insert_reembolso_alocacao.call_count, 2)

    def test_no_pending_expenses_raises(self):
        self.repo.list_despesas_pendentes_por_desembolsante.return_value = []
        with self.assertRaises(svc.ExpenseServiceError):
            svc.registrar_reembolso(self.db, desembolsante_id=7, data_reembolso="2026-09-02", criado_em="2026-09-02T10:00:00")

    def test_informed_value_must_match_pending_total(self):
        self.repo.list_despesas_pendentes_por_desembolsante.return_value = [{"id": 1, "saldo_pendente": 180}]
        with self.assertRaises(svc.ExpenseServiceError):
            svc.registrar_reembolso(
                self.db, desembolsante_id=7, data_reembolso="2026-09-02",
                criado_em="2026-09-02T10:00:00", valor=999,
            )

    def test_duplicate_registro_uid_is_idempotent(self):
        existing = {"id": 50, "valor": 300}
        self.repo.find_reembolso_by_registro_uid.return_value = existing
        result = svc.registrar_reembolso(
            self.db, desembolsante_id=7, data_reembolso="2026-09-02",
            criado_em="2026-09-02T10:00:00", registro_uid="abc-123",
        )
        self.assertIs(result, existing)
        self.repo.insert_reembolso.assert_not_called()


class CancelarReembolsoTests(unittest.TestCase):
    """Fase 3: cancelar um reembolso lancado por engano reabre a pendencia da despesa
    (soft, auditado -- nunca DELETE)."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)

    def test_cancel_active_reembolso(self):
        self.repo.get_reembolso.return_value = {"id": 50, "status": "confirmado"}
        self.repo.list_reembolso_alocacoes.return_value = [
            {"despesa_id": 1, "valor": 180},
            {"despesa_id": 2, "valor": 120},
        ]
        svc.cancelar_reembolso(self.db, 50, "Lancado para a pessoa errada", "2026-09-03T09:00:00", cancelado_por=1)

        self.repo.cancel_reembolso.assert_called_once_with(
            self.db, 50, "Lancado para a pessoa errada", "2026-09-03T09:00:00", 1
        )
        self.assertEqual(self.repo.insert_evento.call_count, 2)

    def test_cannot_cancel_missing_reembolso(self):
        self.repo.get_reembolso.return_value = None
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_reembolso(self.db, 999, None, "2026-09-03T09:00:00")
        self.repo.cancel_reembolso.assert_not_called()

    def test_cannot_cancel_already_cancelled_reembolso(self):
        self.repo.get_reembolso.return_value = {"id": 50, "status": "cancelado"}
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_reembolso(self.db, 50, None, "2026-09-03T09:00:00")
        self.repo.cancel_reembolso.assert_not_called()


class DuplicateAttachmentTests(unittest.TestCase):
    """Item 20 do pedido: hash identico e sinalizado, decisao fica com o usuario."""

    def test_matching_hash_is_reported(self):
        db = mock.Mock()
        with mock.patch.object(svc, "repo", autospec=True) as repo_mock:
            repo_mock.find_anexo_by_hash.return_value = {"id": 5, "despesa_descricao": "Matricula"}
            result = svc.check_duplicate_anexo(db, "hash-abc", despesa_id=1)
        self.assertEqual(result["despesa_descricao"], "Matricula")
        repo_mock.find_anexo_by_hash.assert_called_once_with(db, "hash-abc", exclude_despesa_id=1)


class MigrateCustoTests(unittest.TestCase):
    """Item 11 do pedido: migracao dos custos existentes, idempotente."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)

    def test_custo_without_value_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.migrate_custo(self.db, {"id": 1, "valor": 0, "descricao": "X"}, "2026-09-02T10:00:00")

    def test_already_migrated_custo_returns_existing_without_duplicating(self):
        existing = {"id": 99, "migrado_de_custo_id": 1}
        self.repo.find_despesa_by_migrado_de_custo.return_value = existing
        result = svc.migrate_custo(self.db, {"id": 1, "valor": 100, "descricao": "X"}, "2026-09-02T10:00:00")
        self.assertIs(result, existing)
        self.repo.insert_despesa.assert_not_called()

    def test_new_custo_creates_despesa_with_full_allocation_and_attachment(self):
        self.repo.find_despesa_by_migrado_de_custo.return_value = None
        self.repo.insert_despesa.return_value = 10
        self.repo.resolve_projeto_cliente.return_value = 42
        self.repo.get_despesa.return_value = {"id": 10}

        custo = {
            "id": 1, "projeto_id": 245, "descricao": "Matricula", "categoria": "MATRICULA",
            "valor": 100, "data_custo": "2026-09-01", "observacoes": None, "status": "a_cobrar",
            "criado_em": "2026-09-01T09:00:00", "usuario_id": 3,
            "anexo_path": "/SC/Pastas/x/Financeiro/comprovante.pdf", "anexo_nome": "comprovante.pdf",
        }
        svc.migrate_custo(self.db, custo, "2026-09-02T10:00:00")

        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["migrado_de_custo_id"], 1)
        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["origem"], "MIGRACAO")
        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["status"], "pronta")
        self.repo.insert_alocacao.assert_called_once_with(self.db, 10, 245, 42, Decimal("100.00"), "2026-09-02T10:00:00")
        self.repo.insert_anexo.assert_called_once()

    def test_cancelled_custo_migrates_as_cancelled(self):
        self.repo.find_despesa_by_migrado_de_custo.return_value = None
        self.repo.insert_despesa.return_value = 11
        self.repo.resolve_projeto_cliente.return_value = None
        self.repo.get_despesa.return_value = {"id": 11}
        custo = {
            "id": 2, "projeto_id": 245, "descricao": "Certidao", "valor": 50,
            "status": "cancelado", "criado_em": "2026-09-01T09:00:00",
        }
        svc.migrate_custo(self.db, custo, "2026-09-02T10:00:00")
        self.assertEqual(self.repo.insert_despesa.call_args.kwargs["status"], "cancelada")

    def test_migrate_pending_skips_already_migrated(self):
        already = {"id": 200, "migrado_de_custo_id": 1}

        def fake_find(db, custo_id):
            return already if custo_id == 1 else None

        self.repo.find_despesa_by_migrado_de_custo.side_effect = fake_find
        self.repo.insert_despesa.return_value = 300
        self.repo.resolve_projeto_cliente.return_value = None
        self.repo.get_despesa.return_value = {"id": 300}

        custos = [
            {"id": 1, "projeto_id": 245, "descricao": "Ja migrado", "valor": 10, "status": "a_cobrar", "criado_em": "x"},
            {"id": 2, "projeto_id": 245, "descricao": "Novo", "valor": 20, "status": "a_cobrar", "criado_em": "x"},
        ]
        migrated = svc.migrate_pending_custos(self.db, custos, "2026-09-02T10:00:00")
        self.assertEqual(migrated, 1)
        self.repo.insert_despesa.assert_called_once()


class ExpenseRepositoryQueryShapeTests(unittest.TestCase):
    """Confere que o repositorio monta SQL/params coerentes contra um FakeDb simples
    (sem depender de banco real), no mesmo estilo de test_representation_service.py."""

    class FakeCursor:
        def __init__(self, rows):
            self._rows = list(rows)

        def fetchone(self):
            return self._rows[0] if self._rows else None

        def fetchall(self):
            return self._rows

        def close(self):
            pass

    class FakeDb:
        def __init__(self, rows=None):
            self.rows = rows if rows is not None else []
            self.executed = []

        def execute(self, sql, params=()):
            self.executed.append((sql, params))
            return ExpenseRepositoryQueryShapeTests.FakeCursor(self.rows)

    def test_insert_despesa_returns_new_id(self):
        db = self.FakeDb(rows=[{"id": 42}])
        despesa_id = repo.insert_despesa(
            db, descricao="Matricula", valor_total=Decimal("300.00"),
            desembolsado_por_tipo="EMPRESA", criado_em="2026-09-02T10:00:00",
        )
        self.assertEqual(despesa_id, 42)
        sql, params = db.executed[0]
        self.assertIn("INSERT INTO despesas", sql)
        self.assertIn("RETURNING id", sql)

    def test_resolve_projeto_cliente_returns_none_when_no_row(self):
        db = self.FakeDb(rows=[])
        self.assertIsNone(repo.resolve_projeto_cliente(db, 245))

    def test_find_anexo_by_hash_returns_none_for_empty_hash(self):
        db = self.FakeDb(rows=[{"id": 1}])
        self.assertIsNone(repo.find_anexo_by_hash(db, ""))
        self.assertEqual(db.executed, [])  # nao bate no banco sem hash

    def test_get_despesas_indicadores_passes_month_range_six_times(self):
        # Item 14 do pedido: total do mes, pago empresa/pessoas no mes usam o
        # mesmo intervalo de datas (inicio/fim), 3 filtros = 6 parametros.
        db = self.FakeDb(rows=[{"total_mes": 8450.0}])
        repo.get_despesas_indicadores(db, "2026-09-01", "2026-09-30")
        sql, params = db.executed[0]
        self.assertIn("FROM despesas d", sql)
        self.assertEqual(params, ("2026-09-01", "2026-09-30") * 3)

    def test_list_fila_lancamento_filters_pending_statuses(self):
        db = self.FakeDb(rows=[{"id": 1, "status": "pendente_classificacao"}])
        repo.list_fila_lancamento(db)
        sql, params = db.executed[0]
        self.assertIn("rascunho", sql)
        self.assertIn("pendente_classificacao", sql)
        self.assertEqual(params[-1], 200)

    def test_list_fila_lancamento_can_scope_to_a_lote(self):
        db = self.FakeDb(rows=[])
        repo.list_fila_lancamento(db, lote_id=9)
        sql, params = db.executed[0]
        self.assertIn("d.lote_id = %s", sql)
        self.assertEqual(params[0], 9)

    def test_list_projetos_do_cliente_uses_owner_and_legacy_fallback(self):
        db = self.FakeDb(rows=[{"id": 245, "codigo": "GEO-001", "nome": "Fazenda X"}])
        result = repo.list_projetos_do_cliente(db, 7)
        self.assertEqual(result[0]["codigo"], "GEO-001")
        sql, params = db.executed[0]
        self.assertIn("projeto_proprietarios", sql)
        self.assertEqual(params, (7, 7))

    def test_find_despesas_com_cobranca_ativa_short_circuits_on_empty_list(self):
        db = self.FakeDb(rows=[{"despesa_id": 1}])
        self.assertEqual(repo.find_despesas_com_cobranca_ativa(db, []), set())
        self.assertEqual(db.executed, [])

    def test_find_despesas_com_cobranca_ativa_returns_a_set(self):
        db = self.FakeDb(rows=[{"despesa_id": 1}, {"despesa_id": 3}])
        result = repo.find_despesas_com_cobranca_ativa(db, [1, 2, 3])
        self.assertEqual(result, {1, 3})

    def test_list_despesas_a_cobrar_por_cliente_only_considers_ready_despesas(self):
        db = self.FakeDb(rows=[{"cliente_id": 7, "total_a_cobrar": 63.0}])
        repo.list_despesas_a_cobrar_por_cliente(db)
        sql, _ = db.executed[0]
        self.assertIn("d.status = 'pronta'", sql)
        self.assertIn("ci.status = 'ativo'", sql)

    def test_cancel_cobranca_and_itens_updates_both_tables(self):
        # Item 13 do redesenho: cancelar precisa espelhar o status nos itens,
        # nao so na cobranca-pai, porque o indice unico e as consultas de "a
        # cobrar" olham para cobranca_itens.status (ver migration fase7).
        db = self.FakeDb(rows=[])
        repo.cancel_cobranca_and_itens(db, 900, "Lancado errado", "2026-09-03T09:00:00", 1)
        self.assertEqual(len(db.executed), 2)
        sql_cobranca, params_cobranca = db.executed[0]
        sql_itens, params_itens = db.executed[1]
        self.assertIn("UPDATE cobrancas", sql_cobranca)
        self.assertIn("'cancelada'", sql_cobranca)
        self.assertEqual(params_cobranca, ("Lancado errado", "2026-09-03T09:00:00", 1, 900))
        self.assertIn("UPDATE cobranca_itens", sql_itens)
        self.assertIn("'cancelado'", sql_itens)
        self.assertEqual(params_itens, (900,))


class ClassificarDespesaRapidaTests(unittest.TestCase):
    """Item 4 do redesenho de Lancamentos: proprietario -> projeto -> alocacao
    de 100% montada sozinha, sem o usuario preencher divisao manualmente."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.get_despesa.return_value = {
            "id": 1, "status": "pendente_classificacao",
            "desembolsado_por_tipo": "EMPRESA", "desembolsado_por_id": None,
        }
        self.repo.resolve_projeto_cliente.return_value = 42

    def test_builds_single_full_allocation_from_project(self):
        svc.classificar_despesa_rapida(
            self.db, 1, descricao="Matricula", valor_total=300, categoria="MATRICULA",
            data_despesa="2026-09-02", observacoes=None, desembolsado_por_tipo="EMPRESA",
            projeto_id=245, atualizado_em="2026-09-02T11:00:00", atualizado_por=1,
        )
        self.repo.insert_alocacao.assert_called_once_with(
            self.db, 1, 245, 42, Decimal("300.00"), "2026-09-02T11:00:00", percentual=None
        )

    def test_missing_project_is_rejected_before_any_write(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.classificar_despesa_rapida(
                self.db, 1, descricao="Matricula", valor_total=300, categoria=None,
                data_despesa="2026-09-02", observacoes=None, desembolsado_por_tipo="EMPRESA",
                projeto_id=None, atualizado_em="2026-09-02T11:00:00",
            )
        self.repo.update_despesa_classificacao.assert_not_called()


class CriarCobrancaTests(unittest.TestCase):
    """Itens 9/10 do redesenho: agrupar despesas 'prontas' de um cliente numa
    cobranca auditavel, nunca deixando a mesma despesa entrar em duas ativas."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)
        self.repo.find_despesas_com_cobranca_ativa.return_value = set()

    def test_creates_cobranca_with_multiple_despesas(self):
        self.repo.list_despesas_a_cobrar_do_cliente.return_value = [
            {"id": 1, "valor_total": Decimal("45.00")},
            {"id": 2, "valor_total": Decimal("18.00")},
        ]
        self.repo.insert_cobranca.return_value = 900
        self.repo.get_cobranca.return_value = {"id": 900, "valor_total": Decimal("63.00")}

        result = svc.criar_cobranca(
            self.db, cliente_id=7, despesa_ids=[1, 2],
            data_cobranca="2026-09-02", criado_em="2026-09-02T10:00:00", criado_por=1,
        )

        self.assertEqual(result, {"id": 900, "valor_total": Decimal("63.00")})
        self.repo.insert_cobranca.assert_called_once_with(
            self.db, 7, Decimal("63.00"), "2026-09-02", "2026-09-02T10:00:00",
            observacoes=None, registro_uid=None, criado_por=1,
        )
        self.assertEqual(self.repo.insert_cobranca_item.call_count, 2)

    def test_duplicate_registro_uid_is_idempotent(self):
        existing = {"id": 900, "valor_total": Decimal("63.00")}
        self.repo.find_cobranca_by_registro_uid.return_value = existing
        result = svc.criar_cobranca(
            self.db, cliente_id=7, despesa_ids=[1, 2],
            data_cobranca="2026-09-02", criado_em="2026-09-02T10:00:00", registro_uid="abc-123",
        )
        self.assertIs(result, existing)
        self.repo.insert_cobranca.assert_not_called()

    def test_empty_selection_is_rejected(self):
        with self.assertRaises(svc.ExpenseServiceError):
            svc.criar_cobranca(
                self.db, cliente_id=7, despesa_ids=[],
                data_cobranca="2026-09-02", criado_em="2026-09-02T10:00:00",
            )
        self.repo.insert_cobranca.assert_not_called()

    def test_despesa_not_eligible_for_this_client_is_rejected(self):
        self.repo.list_despesas_a_cobrar_do_cliente.return_value = [{"id": 1, "valor_total": Decimal("45.00")}]
        with self.assertRaises(svc.ExpenseServiceError):
            svc.criar_cobranca(
                self.db, cliente_id=7, despesa_ids=[1, 999],
                data_cobranca="2026-09-02", criado_em="2026-09-02T10:00:00",
            )
        self.repo.insert_cobranca.assert_not_called()

    def test_despesa_already_in_active_cobranca_is_rejected(self):
        self.repo.list_despesas_a_cobrar_do_cliente.return_value = [{"id": 1, "valor_total": Decimal("45.00")}]
        self.repo.find_despesas_com_cobranca_ativa.return_value = {1}
        with self.assertRaises(svc.ExpenseServiceError):
            svc.criar_cobranca(
                self.db, cliente_id=7, despesa_ids=[1],
                data_cobranca="2026-09-02", criado_em="2026-09-02T10:00:00",
            )
        self.repo.insert_cobranca.assert_not_called()


class CancelarCobrancaTests(unittest.TestCase):
    """Item 10 do redesenho: cancelamento soft devolve as despesas para 'a cobrar'."""

    def setUp(self):
        self.db = mock.Mock()
        patcher = mock.patch.object(svc, "repo", autospec=True)
        self.repo = patcher.start()
        self.addCleanup(patcher.stop)

    def test_cancel_active_cobranca(self):
        self.repo.get_cobranca.return_value = {"id": 900, "status": "ativa"}
        self.repo.list_cobranca_itens.return_value = [
            {"despesa_id": 1, "valor": Decimal("45.00")},
            {"despesa_id": 2, "valor": Decimal("18.00")},
        ]
        svc.cancelar_cobranca(self.db, 900, "Lancado errado", "2026-09-03T09:00:00", cancelado_por=1)

        self.repo.cancel_cobranca_and_itens.assert_called_once_with(
            self.db, 900, "Lancado errado", "2026-09-03T09:00:00", 1
        )
        self.assertEqual(self.repo.insert_evento.call_count, 2)

    def test_cannot_cancel_missing_cobranca(self):
        self.repo.get_cobranca.return_value = None
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_cobranca(self.db, 999, None, "2026-09-03T09:00:00")
        self.repo.cancel_cobranca_and_itens.assert_not_called()

    def test_cannot_cancel_already_cancelled_cobranca(self):
        self.repo.get_cobranca.return_value = {"id": 900, "status": "cancelada"}
        with self.assertRaises(svc.ExpenseServiceError):
            svc.cancelar_cobranca(self.db, 900, None, "2026-09-03T09:00:00")
        self.repo.cancel_cobranca_and_itens.assert_not_called()


class ExpensePermissionsTests(unittest.TestCase):
    """Item 13 do pedido: view e sempre p/ logado; gerenciar e admin/coordenador;
    registrar reembolso e exclusivo de admin -- mais conservador que o
    /financeiro atual (que hoje nao verifica perfil algum), de proposito."""

    def _with_user(self, perfil_acesso):
        ctx = appmod.app.test_request_context("/")
        ctx.push()
        self.addCleanup(ctx.pop)
        appmod.g.user = {"id": 1, "nome": "Teste", "perfil_acesso": perfil_acesso}

    def test_no_user_cannot_view(self):
        ctx = appmod.app.test_request_context("/")
        ctx.push()
        self.addCleanup(ctx.pop)
        self.assertFalse(appmod.can_view_despesas())
        self.assertFalse(appmod.can_manage_despesas())
        self.assertFalse(appmod.can_register_reembolso())

    def test_consulta_can_view_but_not_manage(self):
        self._with_user("consulta")
        self.assertTrue(appmod.can_view_despesas())
        self.assertFalse(appmod.can_manage_despesas())
        self.assertFalse(appmod.can_register_reembolso())

    def test_coordenador_can_manage_but_not_register_reembolso(self):
        self._with_user("coordenador")
        self.assertTrue(appmod.can_view_despesas())
        self.assertTrue(appmod.can_manage_despesas())
        self.assertFalse(appmod.can_register_reembolso())

    def test_admin_can_do_everything(self):
        self._with_user("admin")
        self.assertTrue(appmod.can_view_despesas())
        self.assertTrue(appmod.can_manage_despesas())
        self.assertTrue(appmod.can_register_reembolso())


if __name__ == "__main__":
    unittest.main()

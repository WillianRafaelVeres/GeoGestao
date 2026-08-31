import unittest
import datetime as dt

import psycopg2

import representation_service as svc


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
    def __init__(self, rows=None, raise_error=None):
        self.rows = rows if rows is not None else []
        self.raise_error = raise_error
        self.executed = []
        self.commits = []
        self.rolled_back = False

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if self.raise_error:
            raise self.raise_error
        return FakeCursor(self.rows)

    def commit(self, force=False):
        self.commits.append(force)

    def rollback(self):
        self.rolled_back = True


class LabelDictionariesTests(unittest.TestCase):
    """Item 9/11 do pedido: o formulario nunca deve expor codigos internos."""

    def test_papeis_include_all_required_options(self):
        esperados = {
            "PROCURADOR", "REPRESENTANTE_LEGAL", "INVENTARIANTE", "SOCIO_ADMINISTRADOR",
            "ADMINISTRADOR", "DIRETOR", "SINDICO", "ADMINISTRADOR_JUDICIAL", "CURADOR",
            "TUTOR", "REPRESENTANTE", "OUTRO",
        }
        self.assertEqual(set(svc.PAPEIS_REPRESENTACAO), esperados)

    def test_modos_atuacao_use_plain_language_labels(self):
        self.assertEqual(svc.MODOS_ATUACAO["INDIVIDUAL"], "Pode assinar sozinho")
        self.assertEqual(svc.MODOS_ATUACAO["CONJUNTA"], "Deve assinar em conjunto")
        self.assertEqual(svc.MODOS_ATUACAO["QUALQUER_UM"], "Qualquer um dos representantes pode assinar")

    def test_v2_marker_does_not_allow_legacy_sync_by_absence(self):
        self.assertFalse(svc.legacy_representatives_sync_allowed({"representation_ui_version": "2"}))
        self.assertFalse(svc.legacy_representatives_sync_allowed({"representation_ui_version": " 2 "}))

    def test_missing_v2_marker_preserves_legacy_sync_contract(self):
        self.assertTrue(svc.legacy_representatives_sync_allowed({}))
        self.assertTrue(svc.legacy_representatives_sync_allowed({"representation_ui_version": "1"}))

    def test_representation_view_formats_roles_status_and_validity(self):
        result = svc.representacao_view({
            "ativo": True,
            "vigente": True,
            "principal": True,
            "modo_atuacao": "INDIVIDUAL",
            "validade_fim": "2028-08-15",
            "representantes": [{"nome": "Eduardo Schier", "papel": "INVENTARIANTE"}],
        }, today=dt.date(2026, 8, 31))
        self.assertEqual(result["representantes_label"], "Eduardo Schier")
        self.assertEqual(result["papel_label"], "Inventariante")
        self.assertEqual(result["status_label"], "Vigente")
        self.assertEqual(result["validade_label"], "Válida até 15/08/2028")

    def test_representation_view_does_not_use_color_only_for_inactive_status(self):
        result = svc.representacao_view({"ativo": False, "vigente": False, "representantes": []})
        self.assertEqual(result["status_label"], "Inativa")
        self.assertEqual(result["validade_label"], "Sem prazo informado")

    def test_select_document_representante_prefers_vigente_principal(self):
        result = svc.select_document_representante([
            {"ativo": True, "vigente": False, "representantes": [{"nome": "Antigo", "papel": "PROCURADOR"}]},
            {"ativo": True, "vigente": True, "representantes": [{
                "nome": "Eduardo Schier", "cpf_cnpj": "111", "papel": "INVENTARIANTE",
                "principal": True, "qualificacao_central": {"sexo": "MASCULINO"},
            }]},
        ])
        self.assertEqual(result["nome_completo"], "Eduardo Schier")
        self.assertEqual(result["tipo_representacao"], "INVENTARIANTE")
        self.assertEqual(result["sexo"], "MASCULINO")


class RpcWrapperTests(unittest.TestCase):
    def test_get_contexto_assinatura_stringifies_cliente_id(self):
        db = FakeDb(rows=[{"resultado": {"cliente_id": "7"}}])
        result = svc.get_contexto_assinatura(db, "chave-teste", 7)
        self.assertEqual(result, {"cliente_id": "7"})
        sql, params = db.executed[0]
        self.assertIn("obter_contexto_assinatura_v1", sql)
        self.assertEqual(params, ("7", "chave-teste"))
        self.assertEqual(db.commits, [])

    def test_save_representacao_commits_and_returns_id(self):
        db = FakeDb(rows=[{"resultado": {"representacao_id": "rep-1"}}])
        # Caso Gilson/Rosangela (item 23.C): inicialmente so Gilson e representado.
        dados = {
            "natureza": "PROCURACAO",
            "modo_atuacao": "INDIVIDUAL",
            "representantes": [{"pessoa_id": "solanjo-id", "papel": "PROCURADOR", "principal": True}],
            "representados": [{"cliente_id": 10}],
        }
        result = svc.save_representacao(db, "chave-teste", dados)
        self.assertEqual(result, {"representacao_id": "rep-1"})
        self.assertEqual(db.commits, [True])
        sql, params = db.executed[0]
        self.assertIn("salvar_representacao_assinatura_v1", sql)
        payload, chave = params
        self.assertEqual(chave, "chave-teste")
        # psycopg2.extras.Json guarda o dado original em .adapted
        self.assertEqual(payload.adapted, dados)

    def test_save_representacao_can_add_second_representado(self):
        # Depois de marcar Rosangela, a mesma representacao passa a ter os dois.
        db = FakeDb(rows=[{"resultado": {"representacao_id": "rep-1"}}])
        dados = {
            "representacao_id": "rep-1",
            "modo_atuacao": "INDIVIDUAL",
            "representantes": [{"pessoa_id": "solanjo-id", "papel": "PROCURADOR", "principal": True}],
            "representados": [{"cliente_id": 10}, {"pessoa_id": "rosangela-pessoa-id"}],
        }
        svc.save_representacao(db, "chave-teste", dados)
        _, params = db.executed[0]
        payload, _ = params
        self.assertEqual(len(payload.adapted["representados"]), 2)

    def test_deactivate_representacao_commits(self):
        db = FakeDb(rows=[{"resultado": {"representacao_id": "rep-1", "ativo": False}}])
        result = svc.deactivate_representacao(db, "chave-teste", "rep-1")
        self.assertEqual(result["ativo"], False)
        self.assertEqual(db.commits, [True])

    def test_error_is_translated_and_rolls_back(self):
        db = FakeDb(raise_error=psycopg2.Error("informe ao menos um representado"))
        with self.assertRaises(svc.RepresentationServiceError) as ctx:
            svc.save_representacao(db, "chave-teste", {"representantes": [{"pessoa_id": "x"}], "representados": []})
        self.assertIn("informe ao menos um representado", str(ctx.exception))
        self.assertTrue(db.rolled_back)


if __name__ == "__main__":
    unittest.main()

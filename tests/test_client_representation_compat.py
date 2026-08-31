import unittest
from unittest.mock import Mock, patch

import app as geogestao


class ClientRepresentationCompatibilityTests(unittest.TestCase):
    def _save(self, marker=None, quem_assina="PROCURADOR"):
        data = {
            "cliente_id": "7",
            "tipo_cliente": "PESSOA_FISICA",
            "quem_assina": quem_assina,
            "pf_nome_completo": "Cliente Teste",
            "pf_cpf": "",
        }
        if marker is not None:
            data["representation_ui_version"] = marker
        return geogestao.app.test_request_context("/clients", method="POST", data=data)

    def test_v2_save_does_not_sync_or_delete_legacy_representatives(self):
        execute = Mock()
        with self._save(marker="2"), patch.object(geogestao, "validate_cliente_form", return_value=([], [])), patch.object(geogestao, "execute_db", execute), patch.object(geogestao, "upsert_pessoa_fisica", return_value=11), patch.object(geogestao, "upsert_endereco_pf"), patch.object(geogestao, "upsert_conjuge"), patch.object(geogestao, "upsert_imovel_vinculado"), patch.object(geogestao, "refresh_cliente_status"), patch.object(geogestao, "sync_procuradores") as sync:
            result = geogestao.save_cliente_documental()

        self.assertEqual(result, 7)
        sync.assert_not_called()
        queries = [call.args[0] for call in execute.call_args_list]
        self.assertFalse(any("DELETE FROM procuradores" in query for query in queries))

    def test_missing_marker_keeps_legacy_sync_path(self):
        execute = Mock()
        with self._save(marker=None), patch.object(geogestao, "validate_cliente_form", return_value=([], [])), patch.object(geogestao, "execute_db", execute), patch.object(geogestao, "upsert_pessoa_fisica", return_value=11), patch.object(geogestao, "upsert_endereco_pf"), patch.object(geogestao, "upsert_conjuge"), patch.object(geogestao, "upsert_imovel_vinculado"), patch.object(geogestao, "refresh_cliente_status"), patch.object(geogestao, "sync_procuradores") as sync:
            geogestao.save_cliente_documental()

        sync.assert_called_once_with(7, unittest.mock.ANY)


if __name__ == "__main__":
    unittest.main()

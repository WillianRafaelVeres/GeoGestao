import unittest

import psycopg2

import person_repository as repo


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


PESSOAS_FIXTURE = [
    {
        "pessoa_id": "11111111-1111-1111-1111-111111111111",
        "nome_display": "Eduardo Schier",
        "documento": "111.111.111-11",
        "documento_normalizado": "11111111111",
        "search": "eduardo schier 11111111111",
    },
    {
        "pessoa_id": "22222222-2222-2222-2222-222222222222",
        "nome_display": "Solanjo Antonio Gertler",
        "documento": "222.222.222-22",
        "documento_normalizado": "22222222222",
        "search": "solanjo antonio gertler 22222222222",
    },
    {
        "pessoa_id": "33333333-3333-3333-3333-333333333333",
        "nome_display": "Gilson Mueller Berneck",
        "documento": "333.333.333-33",
        "documento_normalizado": "33333333333",
        "search": "gilson mueller berneck 33333333333",
    },
]


class SearchPessoasTests(unittest.TestCase):
    """search_pessoas e uma funcao pura (sem banco): cobre o requisito de
    'Buscar pessoa' do fluxo de adicionar representante (item 9 do pedido)."""

    def test_empty_term_returns_all_up_to_limit(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "", limit=2)
        self.assertEqual(len(result), 2)

    def test_matches_by_name_ignoring_accents_and_case(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "eduardo")
        self.assertEqual([p["nome_display"] for p in result], ["Eduardo Schier"])

    def test_matches_by_partial_name(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "solanjo")
        self.assertEqual([p["nome_display"] for p in result], ["Solanjo Antonio Gertler"])

    def test_matches_by_document_digits_regardless_of_formatting(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "333.333.333-33")
        self.assertEqual([p["nome_display"] for p in result], ["Gilson Mueller Berneck"])

    def test_no_match_returns_empty_list(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "nome que nao existe")
        self.assertEqual(result, [])

    def test_never_returns_more_than_limit(self):
        result = repo.search_pessoas(PESSOAS_FIXTURE, "", limit=1)
        self.assertEqual(len(result), 1)


class RpcWrapperTests(unittest.TestCase):
    def test_get_pessoa_sends_pessoa_id_and_chave_app(self):
        db = FakeDb(rows=[{"resultado": {"pessoa_id": "abc"}}])
        result = repo.get_pessoa(db, "chave-teste", "abc")
        self.assertEqual(result, {"pessoa_id": "abc"})
        sql, params = db.executed[0]
        self.assertIn("obter_pessoa_assinatura_v1", sql)
        self.assertEqual(params, ("abc", "chave-teste"))
        self.assertEqual(db.commits, [])  # leitura nao faz commit

    def test_save_pessoa_commits_immediately_after_write(self):
        db = FakeDb(rows=[{"resultado": {"pessoa_id": "novo-id"}}])
        result = repo.save_pessoa(db, "chave-teste", {"tipo_pessoa": "PESSOA_FISICA", "nome_exibicao": "Teste"})
        self.assertEqual(result, {"pessoa_id": "novo-id"})
        self.assertEqual(db.commits, [True])
        self.assertFalse(db.rolled_back)

    def test_save_pessoa_rolls_back_and_raises_clean_error_on_failure(self):
        db = FakeDb(raise_error=psycopg2.Error("nome obrigatorio"))
        with self.assertRaises(repo.PersonRepositoryError) as ctx:
            repo.save_pessoa(db, "chave-teste", {})
        self.assertIn("nome obrigatorio", str(ctx.exception))
        self.assertTrue(db.rolled_back)
        self.assertEqual(db.commits, [])

    def test_create_cliente_for_pessoa_commits_after_write(self):
        db = FakeDb(rows=[{"resultado": {"cliente_id": "42", "existente": False}}])
        result = repo.create_cliente_for_pessoa(db, "chave-teste", "abc", {})
        self.assertEqual(result, {"cliente_id": "42", "existente": False})
        self.assertEqual(db.commits, [True])


if __name__ == "__main__":
    unittest.main()

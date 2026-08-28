import unittest

import documental


class LabelTipoRepresentacaoTests(unittest.TestCase):
    def test_defaults_to_procurador_when_unknown(self):
        self.assertEqual(documental.label_tipo_representacao("", "MASCULINO"), "Procurador")
        self.assertEqual(documental.label_tipo_representacao("PROCURADOR", "FEMININO"), "Procuradora")
        self.assertEqual(documental.label_tipo_representacao("ALGO_NOVO_NAO_MAPEADO", "MASCULINO"), "Procurador")

    def test_inventariante_label_case_eduardo_eliseu(self):
        self.assertEqual(documental.label_tipo_representacao("INVENTARIANTE", "MASCULINO"), "Inventariante")
        self.assertEqual(documental.label_tipo_representacao("inventariante", "MASCULINO"), "Inventariante")

    def test_gendered_labels(self):
        self.assertEqual(documental.label_tipo_representacao("SINDICO", "MASCULINO"), "Síndico")
        self.assertEqual(documental.label_tipo_representacao("SINDICO", "FEMININO"), "Síndica")
        self.assertEqual(documental.label_tipo_representacao("SOCIO_ADMINISTRADOR", "FEMININO"), "Sócia-administradora")


class QualificacaoComRepresentanteTests(unittest.TestCase):
    """Casos reais descritos no pedido: o papel nunca vira caracteristica fixa
    da pessoa, e o texto de qualificacao usa o representante principal com o
    papel correto (item 20/23 do pedido)."""

    def test_pf_representada_por_inventariante_usa_rotulo_correto(self):
        # Caso Eliseu (Espolio) representado por Eduardo como Inventariante.
        context = {
            "cliente": {
                "tipo_cliente": "PESSOA_FISICA",
                "nome_exibicao": "Espólio de Eliseu Schier",
                "quem_assina": "PROCURADOR",
                "tem_procurador": 1,
            },
            "pessoa_fisica": {"nome_completo": "Eliseu Schier", "cpf": "00000000000"},
            "procurador": {
                "nome_completo": "Eduardo Schier",
                "cpf": "11111111111",
                "sexo": "MASCULINO",
                "tipo_representacao": "INVENTARIANTE",
            },
        }
        texto = documental.build_qualificacao_completa(context)
        self.assertIn("Inventariante EDUARDO SCHIER", texto)
        self.assertNotIn("Procurador EDUARDO", texto)

    def test_pj_representada_por_socio_administrador(self):
        context = {
            "cliente": {"tipo_cliente": "PESSOA_JURIDICA", "nome_exibicao": "Empresa XYZ Ltda"},
            "pessoa_juridica": {"razao_social": "Empresa XYZ Ltda", "cnpj": "00000000000100"},
            "procurador": {
                "nome_completo": "Fulano de Tal",
                "cpf": "22222222222",
                "sexo": "MASCULINO",
                "tipo_representacao": "SOCIO_ADMINISTRADOR",
            },
        }
        texto = documental.build_qualificacao_completa(context)
        self.assertIn("Sócio-administrador FULANO DE TAL", texto)

    def test_papel_desconhecido_nao_quebra_geracao_e_cai_no_padrao(self):
        context = {
            "cliente": {"tipo_cliente": "PESSOA_FISICA", "nome_exibicao": "Fulano", "quem_assina": "PROCURADOR", "tem_procurador": 1},
            "pessoa_fisica": {"nome_completo": "Fulano", "cpf": "33333333333"},
            "procurador": {
                "nome_completo": "Ciclano",
                "cpf": "44444444444",
                "sexo": "MASCULINO",
                "tipo_representacao": "PAPEL_QUE_NAO_EXISTE_AINDA",
            },
        }
        # Nao deve levantar excecao mesmo com um papel fora do mapa conhecido.
        texto = documental.build_qualificacao_completa(context)
        self.assertIn("Procurador CICLANO", texto)


if __name__ == "__main__":
    unittest.main()

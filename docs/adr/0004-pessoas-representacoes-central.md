# ADR 0004 - Cadastro central de pessoas e representacoes

Status: aceito

Data: 2026-08-28

## Contexto

O cadastro de clientes tratava "pessoa", "cliente" e "procurador/representante"
como a mesma coisa: uma pessoa que aparecia em dois papeis diferentes (por
exemplo, proprietaria em um caso e inventariante em outro) virava dois
registros sem nenhuma ligacao entre si. O salvamento do bloco de
procuradores tambem apagava e recriava todas as linhas da tabela
`procuradores` a cada edicao do cliente (`DELETE FROM procuradores WHERE
cliente_id = ...` seguido de reinsercao completa).

O banco Supabase de producao ja foi migrado para uma arquitetura que separa:

- **Pessoa** (`pessoas_cadastro`, `pessoas_fisicas_cadastro`,
  `pessoas_juridicas_cadastro`): quem alguem e, independente do papel.
- **Representacao** (`representacoes`, `representacao_representantes`,
  `representacao_representados`): uma relacao juridica especifica -- quem
  representa quem, com que papel, em que documento/validade.

Essa migracao ja aconteceu; nao coube a esta mudanca criar o schema do zero.
O trabalho era adaptar o GeoGestao para usar essa arquitetura sem quebrar o
que ja funcionava (login, projetos, clientes, matriz, documentos).

## Decisao

- Toda leitura/escrita da arquitetura nova passa pelas RPCs
  `public.*_assinatura_v1` ja publicadas (`listar_pessoas_assinatura_v1`,
  `obter_pessoa_assinatura_v1`, `salvar_pessoa_assinatura_v1`,
  `obter_contexto_assinatura_v1`, `salvar_representacao_assinatura_v1`,
  `desativar_representacao_assinatura_v1`, `criar_cliente_para_pessoa_v1`).
  O GeoGestao nunca reimplementa a logica de resolucao de pessoa por
  CPF/CNPJ, nem escreve direto nas tabelas novas.
- Essas RPCs foram encapsuladas em dois modulos novos e finos:
  `person_repository.py` (pessoas centrais + busca) e
  `representation_service.py` (representacoes + vocabulario de papeis/modo de
  atuacao). `app.py` so chama essas funcoes; nenhum SQL de representacao fica
  espalhado pelas rotas.
- As RPCs sao `SELECT funcao(...)` executadas dentro de uma funcao
  `SECURITY DEFINER` que escreve internamente. O heuristico de deteccao de
  escrita do app (que decide se comita a transacao no fim do request, ver
  ADR 0003) nao enxerga escrita em um `SELECT`. Por isso as chamadas de
  escrita desses dois modulos fazem `db.commit(force=True)` explicito logo
  apos a RPC, e `db.rollback()` em caso de erro.
- **Sincronizacao por identidade, nunca DELETE+INSERT em massa**:
  `salvar_representacao_assinatura_v1` (RPC, nao alterada) substitui apenas
  os representantes/representados da UNICA representacao identificada por
  `representacao_id` -- as demais representacoes do cliente ficam intocadas.
  Do lado legado, `sync_procuradores()` em `app.py` foi reescrita para
  UPDATE quando o `id` enviado pelo formulario ja existe, INSERT quando e
  novo, e DELETE somente das linhas que o usuario removeu explicitamente na
  tela -- nunca mais um DELETE de todas as linhas do cliente seguido de
  reinsercao. Isso importa porque `representacao_representantes.
  procurador_legado_id` referencia `procuradores.id` com `ON DELETE SET
  NULL`: apagar e recriar em massa quebrava esse vinculo e forcava
  `private.sincronizar_representacoes_legadas` a recriar a representacao
  legada com um `representacao_id` novo a cada edicao trivial do cadastro
  (por exemplo, so trocar um telefone).
- A chave de aplicacao exigida pelas RPCs (`private.validar_chave_assinaturas`)
  e lida de `GEOGESTAO_ASSINATURAS_APP_KEY` (nova variavel de ambiente); o
  valor nunca fica no codigo, em testes, em log ou nesta documentacao.
- O bootstrap de banco local/dev (`init_db()` / `--init-db`) ganhou um passo
  idempotente (`bootstrap_pessoas_representacoes_schema`) que aplica
  `docs/sql/pessoas_representacoes_schema.sql` -- tabelas, colunas novas,
  triggers de sincronizacao legada e as RPCs, exatamente como ja estao em
  producao. Esse script nunca roda sozinho contra producao: so executa
  dentro de `init_db()`, que por sua vez so roda com `--init-db` ou
  `GEOGESTAO_AUTO_INIT_DB=1` explicitos, e e idempotente (`CREATE TABLE IF
  NOT EXISTS`, `CREATE OR REPLACE FUNCTION`, blocos `DO` checando
  `pg_constraint`).
- A tela de cliente ganhou uma secao "Representacoes" (lista + modal de
  adicionar/editar) que usa busca de pessoa central (`/api/pessoas/search`),
  reaproveitando `pessoa_id` quando a pessoa ja existe, com papel escolhido
  por relacao (nunca fixo na pessoa) e selecao explicita de quem e
  representado (titular e/ou conjuge, sem inferir procuracao do conjuge).
  Tabelas/colunas/rotas legadas (`clientes.quem_assina`, `tem_procurador`,
  a secao antiga de "Procuradores e representantes") continuam existindo e
  funcionando.

## Consequencias

- Uma pessoa (ex.: Eduardo Schier) mantem um unico `pessoa_id` mesmo
  aparecendo como cliente/proprietario em um caso e como representante
  (inventariante, procurador etc.) em outro -- sem duplicacao.
- Editar um campo qualquer do cadastro de um cliente nao apaga mais
  representacoes, representados, papel, validade ou campos novos cadastrados
  por outro fluxo (ex.: um gerador de documentos usando as mesmas RPCs).
- `documental.py` ganhou um mapa de rotulos por papel
  (`label_tipo_representacao`) para nao assumir que todo representante e
  "Procurador": um `tipo_representacao`/`papel` desconhecido cai no rotulo
  padrao em vez de quebrar a geracao de texto.
- Um banco novo (dev/teste) roda `python app.py --init-db` e chega no mesmo
  schema de pessoas/representacoes que a producao, sem migrar producao.

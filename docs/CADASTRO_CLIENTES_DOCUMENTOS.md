# Cadastro de Clientes e Base Documental

Este documento registra a decisao de produto e arquitetura para o cadastro documental de clientes do GeoGestao/TopoFlow.

## 1. Objetivo do cadastro de clientes

O cadastro de clientes e um cadastro-mae. Ele nao serve apenas para salvar nome, telefone e CPF. Ele centraliza dados que serao reutilizados em declaracoes, requerimentos, memorial descritivo, documentos de cartorio e integracoes futuras com templates Word/DOCX.

O objetivo e cadastrar uma vez para evitar redigitacao nos proximos modulos:

- requerimentos de retificacao;
- requerimento especifico Rio Negro;
- declaracao do Art. 213;
- declaracao de responsabilidade do proprietario;
- requerimento de averbacao de certificacao;
- memorial descritivo;
- modelos internos e documentos de cartorio.

## 2. Regras condicionais do formulario

### Pessoa Fisica

Quando o cliente for pessoa fisica, o sistema mostra CPF, dados pessoais, estado civil, regime quando aplicavel e endereco do proprietario. CNPJ e dados de empresa ficam ocultos.

Campos essenciais para documentos:

- nome completo;
- sexo, usado para flexoes de genero;
- CPF;
- estado civil;
- regime de casamento quando casado ou em uniao estavel;
- endereco completo.

### Pessoa Juridica

Quando o cliente for pessoa juridica, o sistema mostra CNPJ, razao social, nome fantasia e endereco da empresa. Pessoa juridica sempre exige procurador/representante, porque a assinatura documental deve ser feita por representante habilitado.

### Conjuge

Para pessoa fisica casada ou em uniao estavel:

- Comunhao Parcial, Comunhao Universal e Participacao Final nos Aquestos exigem dados minimos do conjuge.
- Separacao Total de Bens nao exige conjuge por padrao.
- Mesmo em Separacao Total, existe opcao manual para incluir dados do conjuge em casos excepcionais.

### Procurador

A secao de procurador aparece quando:

- quem assina e Procurador; ou
- o cliente e Pessoa Juridica.

O procurador deve ter dados pessoais, endereco, e-mail recomendado e texto adicional para habilitacao profissional, por exemplo: profissional habilitado Tec. Agricola, CFTA no 02697139990.

### Endereco

Pessoa fisica usa `enderecos_proprietario`. Pessoa juridica usa o endereco dentro de `pessoas_juridicas`. Procurador tem endereco proprio em `procuradores`.

### Imoveis

Clientes e imoveis possuem relacao N:N. Um cliente pode ter varios imoveis e um imovel pode ter varios proprietarios, coproprietarios, interessados ou representantes.

### Memorial e geodesicos

Os dados de memorial ficam no imovel e na tabela de vertices. A tabela de vertices nao possui limite artificial de linhas.

## 3. Campos necessarios por categoria

### Dados gerais

- tipo_cliente;
- nome_exibicao;
- quem_assina;
- status_cadastro;
- observacoes;
- criado_em;
- atualizado_em.

### Pessoa Fisica

- sexo;
- nome_completo;
- nacionalidade;
- estado_civil;
- regime_casamento;
- profissao_ocupacao;
- RG;
- orgao expedidor do RG;
- CPF;
- nome do pai;
- nome da mae;
- data de nascimento;
- UF e cidade de nascimento;
- e-mail;
- telefone.

### Conjuge

- sexo;
- nome completo;
- CPF;
- profissao/ocupacao;
- nacionalidade;
- RG;
- orgao expedidor;
- UF e cidade de nascimento;
- data de nascimento.

### Pessoa Juridica

- razao social;
- nome fantasia;
- CNPJ;
- logradouro;
- UF;
- cidade;
- bairro;
- CEP;
- numero;
- complemento;
- e-mail;
- telefone.

### Endereco

- logradouro;
- UF;
- cidade;
- bairro;
- CEP;
- numero;
- complemento.

### Procurador

- sexo;
- nome completo;
- estado civil;
- regime de casamento;
- profissao/ocupacao;
- nacionalidade;
- RG;
- orgao expedidor;
- CPF;
- nome do pai;
- nome da mae;
- data de nascimento;
- UF e cidade de nascimento;
- e-mail;
- texto adicional/habilitacao;
- endereco completo.

### Imovel

- nome do imovel/projeto;
- nome do terreno;
- cartorio/comarca;
- CNS do cartorio;
- tipo de certidao;
- numero da certidao;
- estado e cidade do imovel;
- localidade/denominacao;
- valor do imovel terra nua;
- area antiga m2;
- nova area m2;
- perimetro m;
- codigo de certificacao SIGEF;
- codigo SNCR;
- estrada de acesso;
- ponto de referencia;
- distancia ate ponto de referencia.

### Vertices

- ordem;
- codigo do vertice;
- longitude;
- latitude;
- altitude;
- codigo do vertice destino;
- azimute;
- distancia;
- confrontacao.

## 4. Relacao com documentos futuros

O cadastro alimentara os seguintes modelos:

- RR Geral;
- RR Rio Negro;
- Declaracao Art. 213;
- Declaracao Art. 213 RN;
- Declaracao de Responsabilidade do Proprietario;
- Requerimento de Averbacao de Certificacao;
- Memorial Descritivo.

Os placeholders antigos dos templates Word devem ser preservados em uma camada de compatibilidade, nao como campos textuais gravados diretamente no banco.

## 5. Regra de campos obrigatorios

Nem todo campo deve bloquear o cadastro. O sistema deve permitir salvar rascunho incompleto.

A obrigatoriedade forte ocorre somente no momento de gerar um documento especifico. Cada documento possui seus requisitos em `document_field_requirements` e no mapeamento de codigo.

O sistema deve indicar:

- cadastro basico completo;
- dados para documentos incompletos;
- pronto para gerar RR Geral;
- pronto para gerar Declaracao Art. 213;
- pronto para gerar Memorial;
- faltando procurador;
- faltando imovel;
- faltando conjuge;
- faltando cartorio;
- faltando matricula/certidao.

## 6. Campos derivados

Campos derivados devem ser gerados por codigo:

- textos de qualificacao;
- flexoes de genero;
- texto do proprietario;
- texto do conjuge;
- texto do procurador;
- assinatura;
- linha do conjuge;
- textos de documentos;
- contexto de placeholders.

Funcoes previstas:

- `buildDocumentoContext(cliente, imovel)`;
- `buildTextoProprietario(cliente, imovel)`;
- `buildAssinaturas(cliente)`;
- `buildTextoProcurador(cliente)`;
- `buildTextoConjuge(cliente)`;
- `buildFlexoesGenero(sexo)`;
- `getMissingFieldsForDocument(tipoDocumento, cliente, imovel)`;
- `canGenerateDocument(tipoDocumento, cliente, imovel)`.

## 7. Decisao importante sobre genero

As flexoes de genero nao devem ser armazenadas no banco.

O banco guarda apenas dados objetivos, como `sexo`. O texto flexionado deve ser gerado por codigo para evitar inconsistencias e permitir melhoria futura da redacao.

Exemplo:

- masculino: brasileiro, casado, portador, inscrito, proprietario, filho de, residente e domiciliado;
- feminino: brasileira, casada, portadora, inscrita, proprietaria, filha de, residente e domiciliada.

## 8. Compatibilidade com a antiga aba BD_Dados

Todos os campos principais da antiga aba `BD_Dados` estao contemplados no modelo novo:

- dados de empresa ficam em `pessoas_juridicas`;
- dados do proprietario PF ficam em `pessoas_fisicas`;
- dados do conjuge ficam em `conjuges`;
- endereco PF fica em `enderecos_proprietario`;
- dados de procurador ficam em `procuradores`;
- dados de imovel ficam em `imoveis`;
- dados de memorial ficam em `vertices_imovel`.

## 9. Validacao e consulta de CPF e CNPJ

### CPF — validacao local

O sistema valida CPF apenas localmente, por dígitos verificadores.

Por segurança e privacidade, nenhuma consulta externa de dados pessoais por CPF e realizada. O sistema nao busca nome, data de nascimento, endereco ou filiacao a partir do CPF.

Comportamento:
- Aplica mascara 000.000.000-00 durante a digitacao.
- Quando atingir 11 digitos, valida imediatamente.
- Se invalido, exibe "Informe um CPF valido." no campo.
- Se valido, exibe "CPF valido." discretamente.
- Nenhuma API externa e chamada.

### CNPJ — validacao local + consulta de dados publicos empresariais

O sistema valida CNPJ localmente por dígitos verificadores. Se valido, consulta dados cadastrais publicos da empresa via BrasilAPI.

Dados cadastrais de empresas sao informacoes publicas. Isso economiza tempo, reduz erros de digitacao e agiliza o cadastro de Pessoa Juridica.

Comportamento:
- Aplica mascara 00.000.000/0000-00 durante a digitacao.
- Quando atingir 14 digitos e for valido, consulta a BrasilAPI com debounce de 400ms.
- Exibe "Consultando CNPJ..." durante a busca.
- Se encontrado: preenche automaticamente razao social, nome fantasia, logradouro, numero, bairro, cidade, UF e CEP. Complemento nao e preenchido automaticamente (fica manual). Telefone e email sao preenchidos apenas se o campo estiver vazio.
- Se nao encontrado: exibe "CNPJ valido, mas nao encontrado na consulta. Preencha manualmente."
- Se a API falhar: exibe "Nao foi possivel consultar o CNPJ agora. Voce pode preencher manualmente." O cadastro nao e bloqueado.
- Consultas ao mesmo CNPJ sao cacheadas em memoria por sessao para evitar chamadas repetidas.

Endpoint utilizado:
  GET https://brasilapi.com.br/api/cnpj/v1/{cnpj}

## 10. Arquitetura central de pessoas e representacoes

Desde 2026-08 o banco Supabase de producao possui uma camada central que
separa quatro conceitos que antes eram tratados como a mesma coisa. Ver
detalhes tecnicos completos em [`docs/adr/0004-pessoas-representacoes-central.md`](adr/0004-pessoas-representacoes-central.md).

- **Pessoa** (`pessoas_cadastro` + `pessoas_fisicas_cadastro` /
  `pessoas_juridicas_cadastro`): a identidade. Nome, CPF/CNPJ, dados de
  qualificacao. Existe uma unica vez, reutilizada onde quer que a pessoa
  apareca.
- **Cliente** (`clientes` e as tabelas legadas ja documentadas acima):
  contexto cadastral/comercial/documental. E o "caso" que a SC Topografia
  atende -- pode ter `pessoa_id` apontando para a pessoa central.
- **Proprietario**: o papel que uma pessoa exerce em um imovel/projeto/
  documento especifico. Nao e um cadastro separado; e uma qualificacao
  dentro do contexto do cliente/imovel.
- **Representante**: a relacao entre duas ou mais pessoas/partes
  (`representacoes`, `representacao_representantes`,
  `representacao_representados`). Registra quem representa quem, com que
  papel (procurador, inventariante, sindico, socio-administrador etc.), em
  que documento e por quanto tempo.

Pessoa != Cliente != Proprietario != Representante. A mesma pessoa pode
ocupar papeis diferentes em contextos diferentes sem nunca virar um segundo
cadastro:

> Eduardo Schier tem um unico `pessoa_id`. Em um caso ele e o proprietario
> (cliente com `pessoa_id` apontando para ele). Em outro caso -- o
> inventario do Espolio de Eliseu Schier -- ele e o representante, com
> papel Inventariante. Abrir o cadastro de Eduardo nao mostra "Inventariante"
> como caracteristica permanente dele; isso so aparece na secao
> "Representacoes" do cliente que ele representa (no caso, o Espolio de
> Eliseu Schier).

O cliente ganhou dois campos novos para casos como esse:

- `condicao_juridica`: `NORMAL`, `ESPOLIO` ou `OUTRO`.
- `nome_documental`: nome a usar nos documentos quando difere do nome da
  pessoa historica -- ex.: cliente e Eliseu Schier (pessoa), condicao
  `ESPOLIO`, nome documental "Espolio de Eliseu Schier". A pessoa historica
  (Eliseu) continua sendo Eliseu; nao se cria uma pessoa artificial chamada
  "Espolio de Eliseu Schier".

Na tela de cliente, a secao "Representacoes" (dentro do mesmo modal de
cadastro, sem redesenho geral) lista as representacoes ativas daquele
cliente e do respectivo conjuge, e permite adicionar uma nova: buscar a
pessoa no cadastro central (por nome, CPF ou CNPJ) reaproveitando o
`pessoa_id` se ja existir, escolher o papel daquela relacao especifica,
marcar explicitamente quem e representado (o titular e/ou o conjuge -- a
procuracao do conjuge nunca e inferida automaticamente) e o modo de atuacao
em linguagem simples ("Pode assinar sozinho" / "Deve assinar em conjunto" /
"Qualquer um dos representantes pode assinar"). Campos avancados (documento
base, escopo de poderes, validade, observacoes) ficam em uma secao
recolhivel para nao atrapalhar o fluxo normal.

O modulo `person_repository.py` encapsula a busca/leitura/escrita de pessoas
centrais; `representation_service.py` encapsula representacoes e os
vocabularios de papel/modo de atuacao. Ambos delegam tudo as RPCs
`public.*_assinatura_v1` ja publicadas no Supabase -- nenhum dos dois
reimplementa a logica de resolucao de pessoa por documento, nem faz
DELETE+INSERT em massa das representacoes de um cliente.

### 10.1 Experiencia de assinatura e compatibilidade

O modal apresenta uma unica secao de **Assinatura e representacao**. O campo
legado `clientes.quem_assina` continua no formulario e conserva os valores
`PROPRIETARIO` e `PROCURADOR`, mas recebe textos mais claros para o usuario.
Representacoes centrais aparecem em cards com representante, papel, status,
modo de atuacao e validade.

O formulario normal envia `representation_ui_version=2`. O salvamento
cadastral nao interpreta a ausencia dos campos legados `rep_*` como remocao;
essa protecao evita perder procuradores ou vinculos ao editar apenas telefone,
endereco ou outro dado do cliente. O fluxo legado permanece disponivel somente
como **Modo de compatibilidade** quando a chave/RPC da camada central estiver
indisponivel. Nenhuma alteracao de schema e necessaria para essa decisao.

## 11. Proxima etapa

Quando a geracao de documentos for implementada, ela deve consumir `DocumentoContext`, validar os requisitos do documento escolhido e entao preencher o DOCX. A tela de cadastro nao deve armazenar textos prontos de documentos; ela deve armazenar os fatos que permitem gerar esses textos.

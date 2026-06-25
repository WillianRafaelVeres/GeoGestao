# GeoGestao Topografia

Prototipo funcional em Flask para validar a ideia do sistema de gestao de projetos de topografia descrita no documento tecnico.

## Funcionalidades do prototipo

- Login com perfis basicos: administrador, coordenador, tecnico e consulta.
- Dashboard operacional com projetos ativos, atrasos, prazos proximos, gargalos e exigencias externas.
- Matriz visual de projetos x etapas macro, com celulas clicaveis e painel lateral de edicao.
- Cadastro de projetos com criacao automatica de etapas e checklists padrao.
- Tela completa do projeto com resumo, etapas, tarefas, documentos/checklists, cartorio, tempo e historico.
- Minhas missoes com fila pessoal e acoes rapidas de iniciar, pausar e concluir.
- Cadastros de clientes, cartorios/orgaos e usuarios.
- Controle de exigencias de cartorio/orgao externo, com prazos e responsaveis.
- Apontamento simples de tempo por projeto, etapa, tarefa e usuario.
- Relatorios iniciais de gargalo, status, tempo e projetos por cidade.
- Historico automatico para alteracoes importantes.
- Link para abrir a pasta cadastrada do projeto.

## Como rodar

1. Instale as dependencias:
   ```bash
   python -m pip install -r requirements.txt
   ```

2. Configure o banco online no arquivo `.env`:
   ```env
   DATABASE_URL=postgresql://...
   GEOGESTAO_SECRET_KEY=troque-esta-chave
   GEOGESTAO_AUTO_INIT_DB=0
   ```

   No Supabase, copie a connection string em **Project Settings > Database > Connection string**.
   Se a URL direta `db.<projeto>.supabase.co` falhar no Windows com erro de DNS, use a URL do **Connection Pooler** do Supabase.

3. Inicialize/migre o banco apenas quando necessario:
   ```bash
   python app.py --init-db
   ```

4. Execute o servidor:
   ```bash
   python app.py
   ```

5. Acesse:
   ```text
   http://127.0.0.1:5000
   ```

## Deploy online gratuito para desenvolvimento

O caminho mais simples agora e:

- Banco: Supabase Free, usando o Pooler IPv4 na `DATABASE_URL`.
- Aplicacao Flask: Render Web Service Free.

No Render:

1. Conecte este repositorio GitHub.
2. Crie um **Web Service**.
3. Use:
   ```bash
   python -m pip install -r requirements.txt
   ```
   como build command.
4. Use:
   ```bash
   gunicorn app:app --workers 1 --threads 4 --timeout 120
   ```
   como start command.
5. Cadastre as variaveis de ambiente:
   ```text
   DATABASE_URL=postgresql://...
   GEOGESTAO_SECRET_KEY=uma-chave-secreta-forte
   GEOGESTAO_DEBUG=0
   GEOGESTAO_AUTO_INIT_DB=0
   ```

O arquivo `render.yaml` ja deixa essa configuracao preparada. Nao envie o arquivo `.env` para o GitHub; ele deve existir somente na maquina local.

## Credenciais de demonstracao

- Gestor: `admin@geogestao.local` / `admin123`
- Coordenador: `marcos@geogestao.local` / `coord123`
- Tecnico: `rafael@geogestao.local` / `tecnico123`

## Estrutura

- `app.py`: backend Flask, rotas, inicializacao do schema PostgreSQL/Supabase e regras do prototipo.
- `templates/`: telas HTML/Jinja.
- `static/style.css`: interface visual.
- `static/app.js`: comportamento pequeno da interface.
- `Documento_Tecnico_GeoGestao_Topografia.docx`: documento de produto usado como base.

## Proximos passos tecnicos

- Separar o backend em blueprints/services quando o fluxo estiver validado.
- Evoluir migrations e observabilidade do PostgreSQL/Supabase conforme houver usuarios reais simultaneos.
- Criar testes automatizados para regras de prazo, permissoes e historico.
- Evoluir abertura de pastas para app desktop com Tauri.
- Integrar notificacoes por e-mail e WhatsApp Business Cloud API em fase posterior.

## Automacoes futuras preparadas

- Ao entrar em Cartorio, criar lembrete de acompanhamento.
- Ao registrar exigencia de cartorio, criar pendencia com prazo.
- Faltando 5 dias para prazo, notificar responsavel.
- Ao vencer, notificar responsavel e gestor.
- Ao concluir uma etapa, sugerir a proxima etapa.
- Ao ficar parado por X dias na mesma etapa, marcar como atencao.
- Futuramente enviar alertas via WhatsApp Business API.

## Backlog futuro

1. Visao Kanban secundaria por etapa.
2. Visao Calendario para prazos.
3. Visao Timeline/Gantt para projetos maiores.
4. Dashboard de gargalos e tempo medio por etapa.
5. Registro de tempo em status por etapa.
6. Campos customizados por tipo de servico.
7. Modelos de projeto por servico.
8. Checklist documental por tipo de servico.
9. Automacao de criacao de estrutura de pastas.
10. Integracao futura com WhatsApp Business API.
11. Relatorios PDF para o gestor.
12. Historico completo de movimentacoes.
13. Controle de produtividade por responsavel.
14. Registro de exigencias de cartorio.
15. Anexos/documentos por projeto.
16. Permissoes por perfil.
17. Exportacao para Excel.
18. Importacao de projetos via planilha.
19. Campos obrigatorios configuraveis.
20. Painel de projetos parados.

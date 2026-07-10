# Integracao Dropbox

Data: 2026-07-07

## O que faz

O botao "Abrir pasta" (projetos, detalhe do projeto e minhas missoes) abre a pasta do
projeto pelo Dropbox quando o app esta hospedado (Render):

1. Se o servidor Flask roda na maquina do usuario (instalacao local no Windows),
   abre direto no Windows Explorer — inclusive localizando a pasta sincronizada
   do Dropbox pelo `info.json` oficial (`%APPDATA%\Dropbox\info.json`).
2. Hospedado no Render, a rota `/api/open-folder` devolve `{"url": ...}` apontando
   para a pasta em `dropbox.com`, aberta em nova aba. Quem tem o app desktop do
   Dropbox instalado abre no Explorer a partir da pagina; quem nao tem navega online.
   Nao existe URL oficial do Dropbox que abra o Explorer direto do navegador.

## Caminhos aceitos em `caminho_pasta`

- Caminho local sincronizado: `C:\SC Dropbox\SC\Pastas\PASTA 500 Fulano`
  (tudo apos a pasta `* Dropbox` vira o caminho na API: `/SC/Pastas/PASTA 500 Fulano`).
- Caminho Dropbox direto: `/SC/Pastas/PASTA 500 Fulano`.
- Link do dropbox.com colado inteiro: aberto como esta.
- Caminhos antigos fora dos aliases (`\\wdserver\...` ou outras unidades): continuam
  com o comportamento antigo (so abrem quando o app roda local e a pasta existe).
- Caminhos mapeados por alias: por padrao `Y:\PASTAS`, `Z:\PASTAS` e `X:\PASTAS`
  sao tratados como `/SC/Pastas`. Ajuste `DROPBOX_PATH_ALIASES` se a equipe usar
  outro mapeamento. Exemplo:
  `DROPBOX_PATH_ALIASES=Y:\PASTAS=/SC/Pastas;W:\CLIENTES=/SC/Clientes`.

## Credenciais e conta

- App "GeoGestao" no Dropbox App Console (Scoped access, Full Dropbox), autorizado
  pela conta Willian (Dropbox Business, equipe "SC").
- Escopos: `account_info.read`, `files.metadata.read`, `sharing.read`, `sharing.write`.
  Sem `files.content.*`: o token nao le nem altera conteudo de arquivos.
- Env vars (no `.env` local e no dashboard do Render):
  `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`.
  O refresh token nao expira; o access token e renovado em memoria pela aplicacao.

## Detalhe tecnico importante (Business)

Toda chamada de arquivos usa o header `Dropbox-API-Path-Root` com o
`root_namespace_id` da equipe. Sem ele, caminhos como `/SC/Pastas/...` dao
`path/not_found`, porque a API resolve na pasta pessoal do membro.

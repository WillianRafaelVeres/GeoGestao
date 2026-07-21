# Estudo: leitura automatica de nota de exigencia

Data: 2026-07-21

## Conclusao

O fluxo de teste esta ativo. Depois que a nota e validada, deduplicada, versionada e
enviada ao Dropbox, um usuario pode solicitar um rascunho de checklist, revisar cada
item e confirmar sua inclusao. A IA nunca conclui itens nem movimenta o projeto.

## Fluxo recomendado

1. Extrair o texto diretamente quando o PDF ja possui camada de texto.
2. Aplicar OCR quando o documento for uma digitalizacao ou fotografia.
3. Separar cada exigencia em um item estruturado, preservando pagina e trecho de origem.
4. Mostrar os itens como rascunho para revisao humana.
5. Criar o checklist somente depois da confirmacao do usuario.

## Motivos para exigir revisao

- notas podem conter carimbos, manuscritos, tabelas e imagens com baixa qualidade;
- um item pode conter varias providencias dependentes;
- datas, numeros de matricula e nomes nao podem ser inferidos incorretamente;
- o documento pode conter dados pessoais e registrais.

## Implementacao segura

- processar apenas arquivos permitidos e limitar tamanho e quantidade de paginas;
- nao expor credenciais do Dropbox ao navegador;
- nao armazenar o texto integral extraido; guardar apenas o rascunho revisavel e a auditoria;
- registrar o mecanismo usado e a confirmacao do usuario;
- nunca concluir itens ou movimentar o projeto automaticamente;
- impedir a aplicacao duplicada do mesmo rascunho com bloqueio transacional;
- manter o cadastro manual disponivel quando o provedor estiver indisponivel.

## Componentes da versao de teste

- PyMuPDF para extracao local de texto e renderizacao de paginas escaneadas;
- Groq `openai/gpt-oss-120b` para estruturar texto em JSON;
- Groq `qwen/qwen3.6-27b` para leitura de paginas sem camada de texto;
- Supabase para guardar somente o rascunho, metadados de uso e confirmacao;
- revisao humana obrigatoria antes de criar registros em `exigencia_itens`.

## Referencias tecnicas

- PyMuPDF: https://pymupdf.readthedocs.io/
- Groq Structured Outputs: https://console.groq.com/docs/structured-outputs
- Groq Images and Vision: https://console.groq.com/docs/vision
- Groq Data Controls: https://console.groq.com/docs/your-data

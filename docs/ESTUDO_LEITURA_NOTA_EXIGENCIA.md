# Estudo: leitura automatica de nota de exigencia

Data: 2026-07-21

## Conclusao

E tecnicamente possivel preencher uma proposta de checklist a partir da nota anexada.
Esta automacao nao esta ativa nesta entrega. O arquivo apenas e validado, deduplicado,
versionado e enviado ao Dropbox.

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

## Implementacao futura segura

- processar apenas arquivos permitidos e limitar tamanho e quantidade de paginas;
- nao expor credenciais do Dropbox ao navegador;
- registrar o texto extraido, o mecanismo usado e a confirmacao do usuario;
- nunca concluir itens ou movimentar o projeto automaticamente;
- oferecer uma opcao explicita de apagar o texto extraido sem apagar o documento original;
- definir com a empresa se o processamento pode usar um servico externo ou deve ocorrer localmente.

## Referencias tecnicas

- pypdf, extracao de texto de PDFs digitais: https://pypdf.readthedocs.io/en/latest/
- OCRmyPDF, camada de texto para PDFs digitalizados: https://ocrmypdf.readthedocs.io/en/latest/
- Tesseract, formatos de imagem suportados: https://tesseract-ocr.github.io/tessdoc/InputFormats.html

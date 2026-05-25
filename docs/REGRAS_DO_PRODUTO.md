# Regras do Produto — GeoGestao Topografia

> Este documento é o guia permanente do projeto. Toda nova funcionalidade, tela ou componente deve responder a estas regras antes de ser implementado.

---

## 1. Princípio central

**O sistema deve ser mais fácil que o método antigo.**

- A matriz de projetos é o coração do sistema. Tudo gira em torno dela.
- O usuário deve conseguir entender a situação da empresa **batendo o olho** na matriz.
- Se uma funcionalidade é bonita mas difícil de usar, ela está errada.
- Se uma tela tem informação demais e exige pensar muito, ela está errada.
- Se o usuário precisa clicar muitas vezes para uma ação simples, está errado.
- Se o sistema exige mais trabalho que o método antigo, ele vai fracassar.

A finalidade do sistema é **modernizar sem assustar**.

---

## 2. Perfil dos usuários

### Equipe operacional
- Pessoas acostumadas ao método antigo da empresa (planilhas, papel, memória).
- Não querem perder tempo preenchendo formulários longos.
- Precisam de clareza e rapidez para registrar avanço de etapa.
- Estão há muitos anos na empresa — têm rotina consolidada.

### Gestores
- Precisam enxergar gargalos, atrasos e responsabilidades em poucos segundos.
- Querem saber: quem está sobrecarregado, qual etapa demora mais, o que está parado.
- Não querem ler relatório — querem olhar e entender.

### Regra de ouro para todos os perfis
> Uma pessoa da empresa deve conseguir usar o sistema sem treinamento longo.

---

## 3. Regras de simplicidade

- **Poucos cliques.** Nenhuma ação importante deve exigir mais de 2 cliques a partir da tela principal.
- **Poucos campos obrigatórios.** Só exigir o que é realmente necessário para registrar.
- **Ações rápidas.** Avançar etapa, registrar pendência, trocar responsável — devem ser imediatos.
- **Linguagem simples.** Sem jargões de software. Usar os termos que a empresa já usa.
- **Visual limpo.** Cada tela deve ter um foco principal. Nada concorre com o que importa.
- **Informações progressivas.** Mostrar pouco primeiro; detalhar só quando o usuário clicar.
- **Nunca poluir a tela principal.** A matriz deve parecer uma planilha profissional, não um painel congestionado.

---

## 4. Regras da matriz

A matriz é a tela principal do sistema. Deve funcionar como uma **tabela operacional profissional**.

### Estrutura das colunas
- **Linha = projeto.**
- **Colunas fixas (sticky):**
  1. Proprietário / Dono
  2. Projeto (nome + código)
  3. Cartório
- **Colunas de etapas** (uma por etapa do fluxo): Orçamento, Documentos, Análise, Medição, Processamento, Escritório, Planta, Documentação, Assinaturas, Cartório, Pendência, Finalizado.

### Célula ativa
- A célula da etapa atual é a única que deve ter conteúdo visível e interativo.
- Deve mostrar: **responsável**, **status** (curto), **prazo** (se houver), **badge de pendência** (se houver).
- Deve ser compacta e legível — não um card grande.
- Cor de fundo suave indicando o estado:
  - Azul suave → em andamento
  - Amarelo suave → aguardando
  - Vermelho suave → atrasado
  - Verde suave → pronto / concluído
  - Roxo suave → retrabalho / pendência

### Células passadas e futuras
- Etapas já concluídas: mostrar apenas `···` discreto. Sem destaque.
- Etapas futuras: vazio. Nada.
- O foco visual deve estar sempre na etapa atual.

### O que o gestor deve enxergar na matriz
- Onde está cada projeto.
- Quem está responsável.
- O que está atrasado.
- O que tem pendência.
- Qual etapa está acumulando mais projetos (gargalo).

---

## 5. Regras de pop-up / modal

- **Ao clicar em um projeto, abrir um modal centralizado na viewport.**
- Não usar drawer lateral (offcanvas) para detalhes principais do projeto.
- O modal deve ficar **no centro da tela visível**, não no centro do documento rolável.
- Se houver 100 projetos e o usuário clicar no primeiro, o modal abre imediatamente no centro da tela. O usuário não precisa rolar nada.
- O fundo escurece levemente (overlay).
- Fechar com X, com Esc, ou clicando fora.
- Largura entre 860px e 1100px em desktop.
- Altura máxima de 85vh. Scroll interno apenas dentro do modal.
- **A página principal não pode rolar** para o usuário encontrar o modal.

### Conteúdo do modal
- Cabeçalho: nome do projeto, proprietário, cartório, etapa atual, status.
- Meta: responsável, prazo, pendências, próximo item do checklist.
- Ações rápidas: Avançar etapa, Retornar etapa, + Pendência, Abrir projeto completo.
- Seções: Checklist, Pendências abertas, Movimentações recentes, Pasta do projeto.
- Não jogar tudo na tela de uma vez. Hierarquia clara de informação.

---

## 6. Regras do dashboard

- O dashboard deve ser **limpo e útil**, não exibicionista.
- Evitar excesso de informações com o mesmo peso visual.
- A primeira leitura deve responder:
  - O que está atrasado?
  - O que vence logo?
  - Quem precisa agir?
  - Onde os projetos estão parados?

### Blocos prioritários (devem aparecer primeiro)
1. Projetos ativos
2. Atrasados
3. Vencendo nos próximos 7 dias
4. Com pendência aberta
5. Sem responsável
6. Em cartório

### Blocos secundários (abaixo ou em drill-down)
- Projetos por etapa
- Projetos por responsável
- Gargalos operacionais
- Cartórios com mais pendências

**Regra:** Não colocar tudo com o mesmo peso visual. Priorizar o que exige ação.

---

## 7. Regras de histórico e retorno de etapa

O sistema deve permitir que um projeto **volte de etapa** sem apagar histórico.

### Toda movimentação deve registrar
- Etapa anterior
- Etapa nova
- Responsável
- Data e hora
- Motivo da movimentação
- Observação livre
- Usuário que realizou a ação

### Tipos de motivo de retorno
- Ajuste interno
- Exigência de cartório
- Falta de documento
- Erro de escritório
- Problema de campo
- Solicitação do cliente

### Na matriz
- Pendências aparecem como badges discretos na célula ativa.
- Retrabalho deve ser visível, mas sem poluir.
- A etapa atual deve continuar clara mesmo com retrabalho.

---

## 8. Regras de pasta do projeto

- Cada projeto pode ter um caminho de pasta vinculado.
- O usuário pode copiar o caminho com um clique.
- O caminho deve ser exibido de forma clara e compacta.
- No futuro (versão desktop): abrir diretamente no Windows Explorer.

---

## 9. Regras de identidade visual

### Evitar
- Visual infantil ou de ferramenta genérica.
- Gradientes exagerados.
- Sombras fortes.
- Cards grandes demais.
- Cores berrantes.
- Emojis na interface.
- Excesso de ícones decorativos.
- Textos com cara de template ("Bem-vindo ao sistema!", etc.).

### Buscar
- Visual limpo, sóbrio e maduro.
- Tabela forte como elemento central.
- Hierarquia tipográfica clara.
- Cores funcionais (status = cor, não decoração).
- Espaçamento bem pensado.
- Botões discretos e diretos.
- Interface adequada para uma empresa de engenharia.

---

## 10. Critérios de sucesso do produto

1. Uma pessoa da empresa consegue usar sem treinamento longo.
2. O gestor entende a operação em menos de 10 segundos olhando para a tela.
3. Registrar avanço de etapa é feito em no máximo 2 cliques.
4. Abrir informações de um projeto é óbvio e imediato.
5. O sistema reduz trabalho — não cria trabalho novo.
6. A equipe sente que o sistema ajuda, não que atrapalha.

---

## 11. O que nunca deve acontecer

- Perda de histórico de qualquer movimentação.
- Campo obrigatório desnecessário bloqueando uma ação simples.
- Modal abrindo fora da área visível da tela.
- Tela principal com mais informação do que o necessário para agir.
- Interface que force o usuário a adaptar o trabalho ao sistema em vez do contrário.
- Build com erros de tipo ou lint antes de qualquer entrega.

---

*Última atualização: 2026-05-25*

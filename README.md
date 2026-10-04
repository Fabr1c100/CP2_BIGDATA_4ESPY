# Sistema de Empréstimo de Livros

Trabalho de Big Data (FIAP). É o backend de um sistema de biblioteca que substitui a planilha de controle de empréstimos. Livros, alunos e empréstimos ficam guardados no MongoDB e a interação é feita por um menu no terminal.

**Integrantes:**
- Nome 1 (RM)
- Nome 2 (RM)
- Nome 3 (RM)

## Como rodar

Precisa de Python 3.10+ e Docker (ou uma conta no MongoDB Atlas).

1. Subir o MongoDB:
   ```
   docker compose up -d
   ```

2. Criar o ambiente virtual e instalar as dependências:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   (no Linux/Mac o segundo comando é `source .venv/bin/activate`)

3. Abrir o menu:
   ```
   python main.py
   ```

4. Rodar os testes:
   ```
   pytest -v
   ```

Os testes usam um banco separado (`biblioteca_test`), que é apagado a cada teste, então os dados do banco `biblioteca` não são afetados.

### Usando o MongoDB Atlas

Se não der para usar o Docker, crie um cluster gratuito no Atlas e defina a string de conexão na variável `MONGO_URI` antes de rodar:

```
$env:MONGO_URI = "mongodb+srv://usuario:senha@cluster.mongodb.net/"
python main.py
```

A string não deve ser colocada no código nem enviada para o GitHub.

## Estrutura

```
db.py            conexão com o MongoDB e criação dos índices
exceptions.py    exceções próprias para os erros de negócio
service.py       regras de negócio (livros, alunos, empréstimos, relatórios)
main.py          menu no terminal
tests/           testes com pytest
docker-compose.yml
```

O `main.py` só lê a entrada e mostra o resultado. Toda regra de negócio está no `service.py`.

## Decisões da equipe

**Estoque no empréstimo.** Para não vender o mesmo exemplar duas vezes, o estoque é baixado com um único `update_one` que filtra `exemplares_disponiveis > 0` e usa `$inc`. O MongoDB faz isso de forma atômica, então se dois alunos pegarem o último exemplar ao mesmo tempo, só um consegue. Existe um teste com várias threads para isso. Se o registro do empréstimo falhar depois da baixa, o exemplar é devolvido ao estoque.

**Empréstimo em aberto.** Um empréstimo sem devolução tem `data_devolucao` nulo. É com esse campo que contamos os empréstimos abertos, verificamos atrasos e bloqueamos a remoção de livros.

**Devolução dupla.** O `update_one` da devolução filtra `data_devolucao: null`. Na segunda tentativa nada é alterado e o sistema lança `EmprestimoJaDevolvido`, sem devolver o exemplar duas vezes ao estoque.

**Data atual como parâmetro.** `emprestar`, `devolver_livro` e o relatório de atrasados recebem o parâmetro `hoje`. Assim os testes simulam atrasos sem esperar dias. No menu, a opção 15 faz o mesmo: avança a data só durante a execução do programa.

**Multa.** R$ 2,00 por dia inteiro depois da `data_prevista`. Devolver no dia do vencimento não gera multa.

**Alterar o total de exemplares.** Ao atualizar `exemplares_total`, a diferença é somada em `exemplares_disponiveis`. Não é permitido reduzir o total abaixo da quantidade de exemplares que estão emprestados. Também não é possível alterar o ISBN de um livro já cadastrado.

**Sem transações.** As operações entre `livros` e `emprestimos` não usam transações do MongoDB (elas exigem replica set). Como a baixa do estoque é feita antes de gravar o empréstimo, o pior caso é um exemplar a menos no estoque se o programa cair no meio do processo, e nunca o contrário.

**Busca.** A busca por título ou autor usa regex sem diferenciar maiúsculas de minúsculas, com `re.escape` para que caracteres como `+` ou `(` digitados pelo usuário não quebrem a consulta.

## Relatórios

Os quatro relatórios usam Aggregation Pipeline:

- 5 livros mais emprestados (`$group`, `$sort`, `$limit`, `$lookup`)
- empréstimos por curso (`$lookup` com alunos e `$group`)
- alunos com empréstimos atrasados e dias de atraso (`$match`, dois `$lookup` e `$dateDiff`, que exige MongoDB 5.0 ou superior)
- total arrecadado em multas (`$group` com `$sum`)
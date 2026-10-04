from datetime import datetime, timedelta

from pymongo.errors import PyMongoError

from db import get_db
from exceptions import BibliotecaError
from service import BibliotecaService

# Data simulada (permite testar atrasos pelo menu sem esperar dias).
# Enquanto for None, o sistema usa a data real.
data_simulada = None


def hoje():
    return data_simulada or datetime.now()


MENU = """
================ BIBLIOTECA ================
 LIVROS
  1  - Cadastrar livro
  2  - Buscar livro por ISBN
  3  - Listar livros
  4  - Atualizar livro
  5  - Remover livro
  8  - Buscar livros (título/autor/categoria)
 ALUNOS
  6  - Cadastrar aluno
  7  - Buscar aluno por matrícula
 EMPRÉSTIMOS
  9  - Emprestar livro
  10 - Devolver livro
 RELATÓRIOS
  11 - Top 5 livros mais emprestados
  12 - Empréstimos por curso
  13 - Alunos com empréstimos atrasados
  14 - Total arrecadado em multas
 OUTROS
  15 - Definir data simulada (teste de atraso)
  0  - Sair
============================================"""


# ----------------------------------------------------------------------
# Funções de entrada e saída
# ----------------------------------------------------------------------
def ler(msg):
    return input(msg).strip()


def ler_int(msg):
    return int(ler(msg))


def mostrar_livro(l):
    print(
        f"ISBN: {l['isbn']} | {l['titulo']} | {l['autor']} | {l['ano']} | "
        f"{l['categoria']} | disponíveis: {l['exemplares_disponiveis']}/{l['exemplares_total']}"
    )


def mostrar_aluno(a):
    print(f"Matrícula: {a['matricula']} | {a['nome']} | {a['curso']} | {a['email']}")


# ----------------------------------------------------------------------
# Ações do menu
# ----------------------------------------------------------------------
def cadastrar_livro(svc):
    svc.cadastrar_livro(
        {
            "isbn": ler("ISBN: "),
            "titulo": ler("Título: "),
            "autor": ler("Autor: "),
            "ano": ler_int("Ano: "),
            "categoria": ler("Categoria: "),
            "exemplares_total": ler_int("Exemplares (total): "),
        }
    )
    print("Livro cadastrado com sucesso.")


def buscar_livro(svc):
    mostrar_livro(svc.buscar_livro(ler("ISBN: ")))


def listar_livros(svc):
    livros = svc.listar_livros()
    if not livros:
        print("Nenhum livro cadastrado.")
    for l in livros:
        mostrar_livro(l)


def atualizar_livro(svc):
    isbn = ler("ISBN do livro: ")
    svc.buscar_livro(isbn)  # confirma que existe antes de pedir os campos
    print("Deixe em branco o que não quiser alterar.")
    campos = {}
    for chave in ("titulo", "autor", "categoria"):
        valor = ler(f"Novo {chave}: ")
        if valor:
            campos[chave] = valor
    for chave in ("ano", "exemplares_total"):
        valor = ler(f"Novo {chave}: ")
        if valor:
            campos[chave] = int(valor)
    if not campos:
        print("Nada para atualizar.")
        return
    mostrar_livro(svc.atualizar_livro(isbn, campos))
    print("Livro atualizado.")


def remover_livro(svc):
    svc.remover_livro(ler("ISBN: "))
    print("Livro removido.")


def buscar_livros(svc):
    termo = ler("Parte do título ou autor (Enter para ignorar): ") or None
    categoria = ler("Categoria (Enter para ignorar): ") or None
    livros = svc.buscar_livros(termo=termo, categoria=categoria)
    if not livros:
        print("Nenhum livro encontrado.")
    for l in livros:
        mostrar_livro(l)


def cadastrar_aluno(svc):
    svc.cadastrar_aluno(
        {
            "matricula": ler("Matrícula: "),
            "nome": ler("Nome: "),
            "curso": ler("Curso: "),
            "email": ler("E-mail: "),
        }
    )
    print("Aluno cadastrado com sucesso.")


def buscar_aluno(svc):
    mostrar_aluno(svc.buscar_aluno(ler("Matrícula: ")))


def emprestar(svc):
    isbn = ler("ISBN: ")
    matricula = ler("Matrícula: ")
    svc.emprestar(isbn, matricula, hoje=hoje())
    print("Empréstimo realizado. Prazo de devolução: 7 dias.")


def devolver(svc):
    isbn = ler("ISBN: ")
    matricula = ler("Matrícula: ")
    multa = svc.devolver_por_isbn_matricula(isbn, matricula, hoje=hoje())
    print("Livro devolvido.")
    if multa > 0:
        print(f"Multa por atraso: R$ {multa:.2f}")
    else:
        print("Sem multa.")


def rel_top_livros(svc):
    resultado = svc.relatorio_top_livros()
    if not resultado:
        print("Ainda não há empréstimos.")
    for i, r in enumerate(resultado, start=1):
        print(f"{i}. {r['titulo']} (ISBN {r['isbn']}): {r['total']} empréstimo(s)")


def rel_por_curso(svc):
    resultado = svc.relatorio_emprestimos_por_curso()
    if not resultado:
        print("Ainda não há empréstimos.")
    for r in resultado:
        print(f"{r['curso']}: {r['total']} empréstimo(s)")


def rel_atrasados(svc):
    resultado = svc.relatorio_atrasados(hoje=hoje())
    if not resultado:
        print("Nenhum aluno com atraso.")
    for r in resultado:
        print(f"{r['aluno']} | {r['livro']} | {r['dias_atraso']} dia(s) de atraso")


def rel_total_multas(svc):
    print(f"Total arrecadado em multas: R$ {svc.relatorio_total_multas():.2f}")


def definir_data():
    global data_simulada
    entrada = ler("Dias a avançar a partir de hoje (0 para voltar à data real): ")
    dias = int(entrada)
    if dias == 0:
        data_simulada = None
        print("Usando a data real.")
    else:
        data_simulada = datetime.now() + timedelta(days=dias)
        print(f"Data simulada: {data_simulada:%d/%m/%Y}")


# ----------------------------------------------------------------------
# Loop principal
# ----------------------------------------------------------------------
def main():
    try:
        svc = BibliotecaService(get_db())
    except PyMongoError as e:
        print("Não foi possível conectar ao MongoDB.")
        print("Verifique se o Docker está rodando (docker compose up -d).")
        print(f"Detalhe: {e}")
        return

    acoes = {
        "1": cadastrar_livro,
        "2": buscar_livro,
        "3": listar_livros,
        "4": atualizar_livro,
        "5": remover_livro,
        "6": cadastrar_aluno,
        "7": buscar_aluno,
        "8": buscar_livros,
        "9": emprestar,
        "10": devolver,
        "11": rel_top_livros,
        "12": rel_por_curso,
        "13": rel_atrasados,
        "14": rel_total_multas,
    }

    while True:
        print(MENU)
        if data_simulada:
            print(f"(Data simulada ativa: {data_simulada:%d/%m/%Y})")
        opcao = ler("Opção: ")

        if opcao == "0":
            print("Até logo!")
            break

        try:
            if opcao == "15":
                definir_data()
            elif opcao in acoes:
                acoes[opcao](svc)
            else:
                print("Opção inválida.")
        except BibliotecaError as e:
            print(f"Erro: {e}")
        except ValueError:
            print("Valor inválido. Digite um número onde for pedido.")
        except PyMongoError as e:
            print(f"Erro no banco de dados: {e}")


if __name__ == "__main__":
    main()
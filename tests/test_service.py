from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest

from exceptions import (
    AlunoComAtraso,
    EmailInvalido,
    EmprestimoJaDevolvido,
    IsbnDuplicado,
    LimiteEmprestimos,
    LivroComEmprestimoAberto,
    LivroIndisponivel,
    LivroNaoEncontrado,
    MatriculaDuplicada,
)

BASE = datetime(2025, 1, 1)  # data fixa para testar atrasos sem esperar dias


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def novo_livro(isbn="111", titulo="Python Fluente", autor="Luciano Ramalho",
               categoria="Programação", total=1, ano=2023):
    return {
        "isbn": isbn,
        "titulo": titulo,
        "autor": autor,
        "ano": ano,
        "categoria": categoria,
        "exemplares_total": total,
    }


def novo_aluno(matricula="2025001", nome="Ana", curso="ADS", email="ana@fiap.com"):
    return {"matricula": matricula, "nome": nome, "curso": curso, "email": email}


# ----------------------------------------------------------------------
# R1 - CRUD de livros
# ----------------------------------------------------------------------
def test_r1_cadastrar_e_buscar_livro(svc):
    svc.cadastrar_livro(novo_livro(total=3))
    livro = svc.buscar_livro("111")
    assert livro["titulo"] == "Python Fluente"
    assert livro["exemplares_disponiveis"] == 3


def test_r1_isbn_duplicado(svc):
    svc.cadastrar_livro(novo_livro())
    with pytest.raises(IsbnDuplicado):
        svc.cadastrar_livro(novo_livro())


def test_r1_buscar_livro_inexistente(svc):
    with pytest.raises(LivroNaoEncontrado):
        svc.buscar_livro("999")


def test_r1_listar_e_atualizar(svc):
    svc.cadastrar_livro(novo_livro(isbn="1", titulo="B"))
    svc.cadastrar_livro(novo_livro(isbn="2", titulo="A"))
    assert [l["titulo"] for l in svc.listar_livros()] == ["A", "B"]

    svc.atualizar_livro("1", {"titulo": "B Novo"})
    assert svc.buscar_livro("1")["titulo"] == "B Novo"


def test_r1_atualizar_total_ajusta_disponiveis(svc):
    svc.cadastrar_livro(novo_livro(total=2))
    svc.atualizar_livro("111", {"exemplares_total": 5})
    livro = svc.buscar_livro("111")
    assert livro["exemplares_total"] == 5
    assert livro["exemplares_disponiveis"] == 5


def test_r1_remover_livro(svc):
    svc.cadastrar_livro(novo_livro())
    svc.remover_livro("111")
    with pytest.raises(LivroNaoEncontrado):
        svc.buscar_livro("111")


def test_r1_nao_remove_livro_com_emprestimo_aberto(svc):
    svc.cadastrar_livro(novo_livro())
    svc.cadastrar_aluno(novo_aluno())
    svc.emprestar("111", "2025001", hoje=BASE)
    with pytest.raises(LivroComEmprestimoAberto):
        svc.remover_livro("111")


# ----------------------------------------------------------------------
# R2 - Alunos
# ----------------------------------------------------------------------
def test_r2_cadastrar_e_buscar_aluno(svc):
    svc.cadastrar_aluno(novo_aluno())
    assert svc.buscar_aluno("2025001")["nome"] == "Ana"


def test_r2_email_invalido(svc):
    with pytest.raises(EmailInvalido):
        svc.cadastrar_aluno(novo_aluno(email="ana.fiap.com"))


def test_r2_matricula_duplicada(svc):
    svc.cadastrar_aluno(novo_aluno())
    with pytest.raises(MatriculaDuplicada):
        svc.cadastrar_aluno(novo_aluno(nome="Outra"))


# ----------------------------------------------------------------------
# R3 - Busca de livros
# ----------------------------------------------------------------------
def test_r3_busca_por_titulo_sem_diferenciar_maiusculas(svc):
    svc.cadastrar_livro(novo_livro(isbn="1", titulo="Python Fluente"))
    svc.cadastrar_livro(novo_livro(isbn="2", titulo="Java Completo", autor="Outro"))
    resultado = svc.buscar_livros(termo="pYtHoN")
    assert [l["isbn"] for l in resultado] == ["1"]


def test_r3_busca_por_autor(svc):
    svc.cadastrar_livro(novo_livro(isbn="1", autor="Machado de Assis"))
    svc.cadastrar_livro(novo_livro(isbn="2", autor="Clarice Lispector"))
    resultado = svc.buscar_livros(termo="machado")
    assert [l["isbn"] for l in resultado] == ["1"]


def test_r3_filtro_por_categoria(svc):
    svc.cadastrar_livro(novo_livro(isbn="1", categoria="Romance"))
    svc.cadastrar_livro(novo_livro(isbn="2", categoria="Técnico"))
    resultado = svc.buscar_livros(categoria="Romance")
    assert [l["isbn"] for l in resultado] == ["1"]


def test_r3_resultados_ordenados_por_titulo(svc):
    svc.cadastrar_livro(novo_livro(isbn="1", titulo="Zebra de Python"))
    svc.cadastrar_livro(novo_livro(isbn="2", titulo="Aprendendo Python"))
    svc.cadastrar_livro(novo_livro(isbn="3", titulo="Meu Python"))
    titulos = [l["titulo"] for l in svc.buscar_livros(termo="python")]
    assert titulos == ["Aprendendo Python", "Meu Python", "Zebra de Python"]


def test_r3_termo_com_caractere_especial_nao_quebra(svc):
    svc.cadastrar_livro(novo_livro(titulo="C++ Avançado"))
    assert len(svc.buscar_livros(termo="c++")) == 1


# ----------------------------------------------------------------------
# R4 - Emprestar
# ----------------------------------------------------------------------
def test_r4_emprestar_reduz_estoque_e_define_prazo(svc):
    svc.cadastrar_livro(novo_livro(total=2))
    svc.cadastrar_aluno(novo_aluno())
    id_emp = svc.emprestar("111", "2025001", hoje=BASE)

    assert svc.buscar_livro("111")["exemplares_disponiveis"] == 1
    emp = svc.db.emprestimos.find_one({"_id": id_emp})
    assert emp["data_prevista"] == BASE + timedelta(days=7)
    assert emp["data_devolucao"] is None


def test_r4_sem_exemplar_disponivel(svc):
    svc.cadastrar_livro(novo_livro(total=1))
    svc.cadastrar_aluno(novo_aluno(matricula="1"))
    svc.cadastrar_aluno(novo_aluno(matricula="2", email="b@fiap.com"))
    svc.emprestar("111", "1", hoje=BASE)
    with pytest.raises(LivroIndisponivel):
        svc.emprestar("111", "2", hoje=BASE)
    assert svc.buscar_livro("111")["exemplares_disponiveis"] == 0


def test_r4_limite_de_3_emprestimos(svc):
    svc.cadastrar_aluno(novo_aluno())
    for i in range(4):
        svc.cadastrar_livro(novo_livro(isbn=str(i), titulo=f"Livro {i}"))
    for i in range(3):
        svc.emprestar(str(i), "2025001", hoje=BASE)
    with pytest.raises(LimiteEmprestimos):
        svc.emprestar("3", "2025001", hoje=BASE)


def test_r4_aluno_com_atraso_nao_pode_emprestar(svc):
    svc.cadastrar_aluno(novo_aluno())
    svc.cadastrar_livro(novo_livro(isbn="1", titulo="Livro 1"))
    svc.cadastrar_livro(novo_livro(isbn="2", titulo="Livro 2"))
    svc.emprestar("1", "2025001", hoje=BASE)
    # 8 dias depois, o prazo de 7 dias já venceu
    with pytest.raises(AlunoComAtraso):
        svc.emprestar("2", "2025001", hoje=BASE + timedelta(days=8))


def test_r4_emprestimos_simultaneos_nao_deixam_estoque_negativo(svc):
    svc.cadastrar_livro(novo_livro(total=1))
    for i in range(5):
        svc.cadastrar_aluno(novo_aluno(matricula=str(i), email=f"a{i}@fiap.com"))

    def tentar(matricula):
        try:
            svc.emprestar("111", matricula, hoje=BASE)
            return True
        except LivroIndisponivel:
            return False

    with ThreadPoolExecutor(max_workers=5) as ex:
        resultados = list(ex.map(tentar, [str(i) for i in range(5)]))

    assert resultados.count(True) == 1
    assert svc.buscar_livro("111")["exemplares_disponiveis"] == 0


# ----------------------------------------------------------------------
# R5 - Devolver
# ----------------------------------------------------------------------
def test_r5_devolucao_no_prazo_sem_multa(svc):
    svc.cadastrar_livro(novo_livro())
    svc.cadastrar_aluno(novo_aluno())
    id_emp = svc.emprestar("111", "2025001", hoje=BASE)

    multa = svc.devolver_livro(id_emp, hoje=BASE + timedelta(days=7))

    assert multa == 0.0
    assert svc.buscar_livro("111")["exemplares_disponiveis"] == 1
    assert svc.db.emprestimos.find_one({"_id": id_emp})["data_devolucao"] is not None


def test_r5_multa_por_atraso(svc):
    svc.cadastrar_livro(novo_livro())
    svc.cadastrar_aluno(novo_aluno())
    id_emp = svc.emprestar("111", "2025001", hoje=BASE)

    # prazo vence em BASE+7; devolvendo em BASE+10 são 3 dias de atraso
    multa = svc.devolver_livro(id_emp, hoje=BASE + timedelta(days=10))

    assert multa == 6.00
    assert svc.db.emprestimos.find_one({"_id": id_emp})["multa"] == 6.00


def test_r5_devolver_duas_vezes_gera_erro(svc):
    svc.cadastrar_livro(novo_livro(total=1))
    svc.cadastrar_aluno(novo_aluno())
    id_emp = svc.emprestar("111", "2025001", hoje=BASE)
    svc.devolver_livro(id_emp, hoje=BASE)

    with pytest.raises(EmprestimoJaDevolvido):
        svc.devolver_livro(id_emp, hoje=BASE)
    # o estoque não pode ter passado do total
    assert svc.buscar_livro("111")["exemplares_disponiveis"] == 1


def test_r5_devolver_por_isbn_e_matricula(svc):
    svc.cadastrar_livro(novo_livro())
    svc.cadastrar_aluno(novo_aluno())
    svc.emprestar("111", "2025001", hoje=BASE)
    multa = svc.devolver_por_isbn_matricula("111", "2025001", hoje=BASE)
    assert multa == 0.0


# ----------------------------------------------------------------------
# R6 - Relatórios
# ----------------------------------------------------------------------
def test_r6_top_livros_mais_emprestados(svc):
    svc.cadastrar_livro(novo_livro(isbn="A", titulo="Livro A", total=5))
    svc.cadastrar_livro(novo_livro(isbn="B", titulo="Livro B", total=5))
    for m in ["1", "2", "3"]:
        svc.cadastrar_aluno(novo_aluno(matricula=m, email=f"{m}@fiap.com"))
    svc.emprestar("A", "1", hoje=BASE)
    svc.emprestar("A", "2", hoje=BASE)
    svc.emprestar("B", "3", hoje=BASE)

    top = svc.relatorio_top_livros()
    assert top[0]["isbn"] == "A"
    assert top[0]["titulo"] == "Livro A"
    assert top[0]["total"] == 2
    assert top[1]["isbn"] == "B"


def test_r6_top_livros_limita_a_5(svc):
    svc.cadastrar_aluno(novo_aluno(matricula="1"))
    # 1 aluno só pega 3 por vez, então usamos vários alunos
    for i in range(6):
        svc.cadastrar_livro(novo_livro(isbn=str(i), titulo=f"L{i}"))
        svc.cadastrar_aluno(novo_aluno(matricula=f"a{i}", email=f"a{i}@fiap.com"))
        svc.emprestar(str(i), f"a{i}", hoje=BASE)
    assert len(svc.relatorio_top_livros()) == 5


def test_r6_emprestimos_por_curso(svc):
    svc.cadastrar_livro(novo_livro(total=5))
    svc.cadastrar_aluno(novo_aluno(matricula="1", curso="ADS", email="1@fiap.com"))
    svc.cadastrar_aluno(novo_aluno(matricula="2", curso="ADS", email="2@fiap.com"))
    svc.cadastrar_aluno(novo_aluno(matricula="3", curso="SI", email="3@fiap.com"))
    for m in ["1", "2", "3"]:
        svc.emprestar("111", m, hoje=BASE)

    por_curso = {r["curso"]: r["total"] for r in svc.relatorio_emprestimos_por_curso()}
    assert por_curso == {"ADS": 2, "SI": 1}


def test_r6_alunos_com_atraso(svc):
    svc.cadastrar_livro(novo_livro(titulo="Python Fluente"))
    svc.cadastrar_aluno(novo_aluno(nome="Ana"))
    svc.emprestar("111", "2025001", hoje=BASE)

    atrasados = svc.relatorio_atrasados(hoje=BASE + timedelta(days=10))

    assert len(atrasados) == 1
    assert atrasados[0]["aluno"] == "Ana"
    assert atrasados[0]["livro"] == "Python Fluente"
    assert atrasados[0]["dias_atraso"] == 3


def test_r6_sem_atrasados_no_prazo(svc):
    svc.cadastrar_livro(novo_livro())
    svc.cadastrar_aluno(novo_aluno())
    svc.emprestar("111", "2025001", hoje=BASE)
    assert svc.relatorio_atrasados(hoje=BASE + timedelta(days=5)) == []


def test_r6_total_de_multas(svc):
    svc.cadastrar_livro(novo_livro(total=5))
    svc.cadastrar_aluno(novo_aluno(matricula="1", email="1@fiap.com"))
    svc.cadastrar_aluno(novo_aluno(matricula="2", email="2@fiap.com"))
    e1 = svc.emprestar("111", "1", hoje=BASE)
    e2 = svc.emprestar("111", "2", hoje=BASE)
    svc.devolver_livro(e1, hoje=BASE + timedelta(days=10))  # 3 dias = R$ 6,00
    svc.devolver_livro(e2, hoje=BASE + timedelta(days=5))   # no prazo = R$ 0,00

    assert svc.relatorio_total_multas() == 6.00


def test_r6_total_de_multas_sem_emprestimos(svc):
    assert svc.relatorio_total_multas() == 0.0
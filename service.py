import re
from datetime import datetime, timedelta

from pymongo.errors import DuplicateKeyError

from exceptions import (
    AlunoComAtraso,
    AlunoNaoEncontrado,
    EmailInvalido,
    EmprestimoJaDevolvido,
    EmprestimoNaoEncontrado,
    IsbnDuplicado,
    LimiteEmprestimos,
    LivroComEmprestimoAberto,
    LivroIndisponivel,
    LivroNaoEncontrado,
    MatriculaDuplicada,
)

PRAZO_DIAS = 7
LIMITE_EMPRESTIMOS = 3
MULTA_POR_DIA = 2.00


class BibliotecaService:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # R1 - CRUD de livros
    # ------------------------------------------------------------------
    def cadastrar_livro(self, dados):
        livro = dict(dados)
        livro["exemplares_disponiveis"] = livro["exemplares_total"]
        try:
            self.db.livros.insert_one(livro)
        except DuplicateKeyError:
            raise IsbnDuplicado(f"ISBN {dados['isbn']} já cadastrado.")
        return livro

    def buscar_livro(self, isbn):
        livro = self.db.livros.find_one({"isbn": isbn})
        if livro is None:
            raise LivroNaoEncontrado(f"Livro com ISBN {isbn} não encontrado.")
        return livro

    def listar_livros(self):
        return list(self.db.livros.find().sort("titulo", 1))

    def atualizar_livro(self, isbn, campos):
        livro = self.buscar_livro(isbn)
        campos = dict(campos)
        # Campos que não podem ser alterados diretamente
        campos.pop("isbn", None)
        campos.pop("exemplares_disponiveis", None)

        update = {}
        if "exemplares_total" in campos:
            # Decisão: a diferença do total é somada ao estoque disponível
            diferenca = campos["exemplares_total"] - livro["exemplares_total"]
            if livro["exemplares_disponiveis"] + diferenca < 0:
                raise ValueError(
                    "Total menor que a quantidade de exemplares emprestados."
                )
            update["$inc"] = {"exemplares_disponiveis": diferenca}
        if campos:
            update["$set"] = campos
        if update:
            self.db.livros.update_one({"isbn": isbn}, update)
        return self.buscar_livro(isbn)

    def remover_livro(self, isbn):
        self.buscar_livro(isbn)
        abertos = self.db.emprestimos.count_documents(
            {"isbn": isbn, "data_devolucao": None}
        )
        if abertos > 0:
            raise LivroComEmprestimoAberto(
                f"O livro {isbn} tem {abertos} empréstimo(s) em aberto."
            )
        self.db.livros.delete_one({"isbn": isbn})

    # ------------------------------------------------------------------
    # R2 - Alunos
    # ------------------------------------------------------------------
    def cadastrar_aluno(self, dados):
        if "@" not in dados.get("email", ""):
            raise EmailInvalido("O e-mail deve conter @.")
        aluno = dict(dados)
        try:
            self.db.alunos.insert_one(aluno)
        except DuplicateKeyError:
            raise MatriculaDuplicada(f"Matrícula {dados['matricula']} já cadastrada.")
        return aluno

    def buscar_aluno(self, matricula):
        aluno = self.db.alunos.find_one({"matricula": matricula})
        if aluno is None:
            raise AlunoNaoEncontrado(f"Aluno {matricula} não encontrado.")
        return aluno

    # ------------------------------------------------------------------
    # R3 - Busca de livros
    # ------------------------------------------------------------------
    def buscar_livros(self, termo=None, categoria=None):
        filtro = {}
        if termo:
            rgx = {"$regex": re.escape(termo), "$options": "i"}
            filtro["$or"] = [{"titulo": rgx}, {"autor": rgx}]
        if categoria:
            filtro["categoria"] = categoria
        return list(self.db.livros.find(filtro).sort("titulo", 1))

    # ------------------------------------------------------------------
    # R4 - Emprestar
    # ------------------------------------------------------------------
    def emprestar(self, isbn, matricula, hoje=None):
        hoje = hoje or datetime.now()

        self.buscar_aluno(matricula)
        self.buscar_livro(isbn)

        atrasados = self.db.emprestimos.count_documents(
            {
                "matricula": matricula,
                "data_devolucao": None,
                "data_prevista": {"$lt": hoje},
            }
        )
        if atrasados > 0:
            raise AlunoComAtraso(f"Aluno {matricula} tem empréstimo atrasado.")

        abertos = self.db.emprestimos.count_documents(
            {"matricula": matricula, "data_devolucao": None}
        )
        if abertos >= LIMITE_EMPRESTIMOS:
            raise LimiteEmprestimos(
                f"Aluno {matricula} já tem {LIMITE_EMPRESTIMOS} empréstimos em aberto."
            )

        # Baixa de estoque atômica
        res = self.db.livros.update_one(
            {"isbn": isbn, "exemplares_disponiveis": {"$gt": 0}},
            {"$inc": {"exemplares_disponiveis": -1}},
        )
        if res.modified_count == 0:
            raise LivroIndisponivel(f"Sem exemplares disponíveis do livro {isbn}.")

        emprestimo = {
            "isbn": isbn,
            "matricula": matricula,
            "data_emprestimo": hoje,
            "data_prevista": hoje + timedelta(days=PRAZO_DIAS),
            "data_devolucao": None,
            "multa": 0.0,
        }
        try:
            res_insert = self.db.emprestimos.insert_one(emprestimo)
        except Exception:
            # Desfaz a baixa de estoque se o registro do empréstimo falhar
            self.db.livros.update_one(
                {"isbn": isbn}, {"$inc": {"exemplares_disponiveis": 1}}
            )
            raise
        return res_insert.inserted_id

    # ------------------------------------------------------------------
    # R5 - Devolver
    # ------------------------------------------------------------------
    def devolver_livro(self, id_emprestimo, hoje=None):
        hoje = hoje or datetime.now()

        emp = self.db.emprestimos.find_one({"_id": id_emprestimo})
        if emp is None:
            raise EmprestimoNaoEncontrado("Empréstimo não encontrado.")

        dias_atraso = max(0, (hoje.date() - emp["data_prevista"].date()).days)
        multa = dias_atraso * MULTA_POR_DIA

        # Só atualiza se ainda não foi devolvido (evita devolução dupla)
        res = self.db.emprestimos.update_one(
            {"_id": id_emprestimo, "data_devolucao": None},
            {"$set": {"data_devolucao": hoje, "multa": multa}},
        )
        if res.modified_count == 0:
            raise EmprestimoJaDevolvido("Este empréstimo já foi devolvido.")

        self.db.livros.update_one(
            {"isbn": emp["isbn"]}, {"$inc": {"exemplares_disponiveis": 1}}
        )
        return multa

    def devolver_por_isbn_matricula(self, isbn, matricula, hoje=None):
        """Versão amigável para o menu: localiza o empréstimo em aberto."""
        emp = self.db.emprestimos.find_one(
            {"isbn": isbn, "matricula": matricula, "data_devolucao": None}
        )
        if emp is None:
            raise EmprestimoNaoEncontrado(
                "Nenhum empréstimo em aberto para esse livro e aluno."
            )
        return self.devolver_livro(emp["_id"], hoje=hoje)

    # ------------------------------------------------------------------
    # R6 - Relatórios (Aggregation Pipeline)
    # ------------------------------------------------------------------
    def relatorio_top_livros(self, limite=5):
        pipeline = [
            {"$group": {"_id": "$isbn", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$limit": limite},
            {
                "$lookup": {
                    "from": "livros",
                    "localField": "_id",
                    "foreignField": "isbn",
                    "as": "livro",
                }
            },
            {"$unwind": "$livro"},
            {
                "$project": {
                    "_id": 0,
                    "isbn": "$_id",
                    "titulo": "$livro.titulo",
                    "total": 1,
                }
            },
        ]
        return list(self.db.emprestimos.aggregate(pipeline))

    def relatorio_emprestimos_por_curso(self):
        pipeline = [
            {
                "$lookup": {
                    "from": "alunos",
                    "localField": "matricula",
                    "foreignField": "matricula",
                    "as": "aluno",
                }
            },
            {"$unwind": "$aluno"},
            {"$group": {"_id": "$aluno.curso", "total": {"$sum": 1}}},
            {"$sort": {"total": -1}},
            {"$project": {"_id": 0, "curso": "$_id", "total": 1}},
        ]
        return list(self.db.emprestimos.aggregate(pipeline))

    def relatorio_atrasados(self, hoje=None):
        hoje = hoje or datetime.now()
        pipeline = [
            {"$match": {"data_devolucao": None, "data_prevista": {"$lt": hoje}}},
            {
                "$lookup": {
                    "from": "alunos",
                    "localField": "matricula",
                    "foreignField": "matricula",
                    "as": "aluno",
                }
            },
            {"$unwind": "$aluno"},
            {
                "$lookup": {
                    "from": "livros",
                    "localField": "isbn",
                    "foreignField": "isbn",
                    "as": "livro",
                }
            },
            {"$unwind": "$livro"},
            {
                "$project": {
                    "_id": 0,
                    "aluno": "$aluno.nome",
                    "livro": "$livro.titulo",
                    "dias_atraso": {
                        "$dateDiff": {
                            "startDate": "$data_prevista",
                            "endDate": hoje,
                            "unit": "day",
                        }
                    },
                }
            },
        ]
        return list(self.db.emprestimos.aggregate(pipeline))

    def relatorio_total_multas(self):
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$multa"}}}]
        resultado = list(self.db.emprestimos.aggregate(pipeline))
        return resultado[0]["total"] if resultado else 0.0
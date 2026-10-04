from pymongo import MongoClient, ASCENDING

URI_PADRAO = "mongodb://localhost:27017"

def get_db(uri=URI_PADRAO, nome="biblioteca"):
    client = MongoClient(uri)
    db = client[nome]
    criar_indices(db)
    return db

def criar_indices(db):
    db.livros.create_index("isbn", unique=True)        # R1
    db.alunos.create_index("matricula", unique=True)   # R2
    db.livros.create_index([("titulo", ASCENDING)])    # R3 (ordenação)
    db.livros.create_index("categoria")                # R3 (filtro)
    db.emprestimos.create_index([("matricula", ASCENDING), ("data_devolucao", ASCENDING)])
    db.emprestimos.create_index([("isbn", ASCENDING), ("data_devolucao", ASCENDING)])
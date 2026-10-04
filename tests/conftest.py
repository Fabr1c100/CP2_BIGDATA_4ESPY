import os
import sys

import pytest
from pymongo import MongoClient

# Permite importar db.py, service.py e exceptions.py da raiz do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import criar_indices  # noqa: E402
from service import BibliotecaService  # noqa: E402

URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
NOME_BANCO_TESTE = "biblioteca_test"


@pytest.fixture
def svc():
    """Serviço ligado a um banco de testes limpo a cada teste."""
    client = MongoClient(URI, serverSelectionTimeoutMS=3000)
    client.drop_database(NOME_BANCO_TESTE)
    db = client[NOME_BANCO_TESTE]
    criar_indices(db)
    yield BibliotecaService(db)
    client.drop_database(NOME_BANCO_TESTE)
    client.close()
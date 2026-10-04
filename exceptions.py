class BibliotecaError(Exception):
    """Base de todos os erros de negócio."""

class LivroNaoEncontrado(BibliotecaError): pass
class AlunoNaoEncontrado(BibliotecaError): pass
class IsbnDuplicado(BibliotecaError): pass
class MatriculaDuplicada(BibliotecaError): pass
class EmailInvalido(BibliotecaError): pass
class LivroComEmprestimoAberto(BibliotecaError): pass
class LivroIndisponivel(BibliotecaError): pass
class LimiteEmprestimos(BibliotecaError): pass
class AlunoComAtraso(BibliotecaError): pass
class EmprestimoNaoEncontrado(BibliotecaError): pass
class EmprestimoJaDevolvido(BibliotecaError): pass
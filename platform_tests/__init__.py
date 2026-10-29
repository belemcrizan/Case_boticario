"""Plataforma via pytest e mocks; unittest preserva o núcleo sem dependências."""


def load_tests(loader, tests, pattern):
    # O protocolo impede discovery recursivo dos módulos opcionais por unittest.
    # Pytest mantém sua coleta normal e executa todos os testes da plataforma.
    return tests

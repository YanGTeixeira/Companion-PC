"""Checagens estáticas do companion_server.py (ele só roda no Windows, com tudo instalado).

As tabelas de ações (ACTIONS, ASYNC_ACTIONS) são montadas no carregamento do módulo: um nome solto nelas
(sem lambda) precisa já estar definido acima, senão o servidor nem abre (NameError). Foi o que quebrou a 1.17.
"""
import ast
import builtins
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "companion_server.py"


class TabelasDeAcoesTest(unittest.TestCase):
    def test_nomes_soltos_ja_definidos(self):
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        defined = set(dir(builtins))
        problems = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith("ACTIONS") for t in node.targets) \
                    and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    for n in ast.walk(v):
                        # nomes fora de lambda são lidos agora; dentro de lambda, só na hora de chamar
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and not _inside_lambda(v, n) and n.id not in defined:
                            problems.append(f"{ast.literal_eval(k) if k else '?'} -> {n.id} (linha {n.lineno})")
            for n in ast.walk(node) if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else []:
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    defined.add(n.id)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                defined.update((a.asname or a.name).split(".")[0] for a in node.names)
        self.assertEqual(problems, [], "usados antes de definidos nas tabelas de ações")


def _inside_lambda(root, target):
    for lam in ast.walk(root):
        if isinstance(lam, ast.Lambda) and any(n is target for n in ast.walk(lam.body)):
            return True
    return False


if __name__ == "__main__":
    unittest.main()

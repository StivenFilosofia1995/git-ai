"""Railway corre Python 3.11 (Dockerfile python:3.11-slim). Este test atrapa sintaxis de 3.12+
que localmente compila pero en producción rompe el import: barras invertidas o las mismas
comillas dentro de las expresiones de un f-string."""
import glob
import io
import os
import sys
import tokenize

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(sys.version_info < (3, 12), reason="el tokenizador de f-strings existe desde 3.12")
def test_fstrings_compatibles_con_python311():
    problemas = []
    for f in glob.glob(os.path.join(RAIZ, "app", "**", "*.py"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            toks = list(tokenize.generate_tokens(io.StringIO(fh.read()).readline))
        pila = []
        for tk in toks:
            if tk.type == tokenize.FSTRING_START:
                pila.append(tk.string.lstrip("rRfFbBuU")[0])
            elif tk.type == tokenize.FSTRING_END:
                pila.pop()
            elif pila and tk.type != tokenize.FSTRING_MIDDLE:
                if "\\" in tk.string:
                    problemas.append(f"{f}:{tk.start[0]} barra invertida dentro de un f-string")
                if tk.type == tokenize.STRING and tk.string.lstrip("rRfFbBuU")[0] in pila:
                    problemas.append(f"{f}:{tk.start[0]} mismas comillas dentro de un f-string")
    assert not problemas, "\n".join(problemas)

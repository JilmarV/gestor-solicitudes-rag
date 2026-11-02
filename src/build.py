import nbformat, sys
sys.path.insert(0,'.')
import cells_a, cells_b, cells_c
nb = nbformat.v4.new_notebook()
for k,t in cells_a.CELLS:
    nb.cells.append(nbformat.v4.new_markdown_cell(t) if k=="md" else nbformat.v4.new_code_cell(t))
nb.metadata = {"kernelspec":{"name":"python3","display_name":"Python 3","language":"python"},"colab":{"provenance":[]},"language_info":{"name":"python"}}
import os; os.makedirs('../notebooks',exist_ok=True)
nbformat.write(nb,'../notebooks/Gestor_Solicitudes_Consolidado.ipynb')
import ast
for i,c in enumerate(nb.cells):
    if c.cell_type=="code":
        src="\n".join(l for l in c.source.splitlines() if not l.startswith("%"))
        ast.parse(src)
print(len(nb.cells),"celdas; sintaxis OK")

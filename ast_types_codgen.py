import subprocess
import sys
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

import trolskgen

# Uncomment this to regenerate `ast_pyi.py` - note some edits have been made
# from mypy import typeshed
# AST_TYPES_PYI = Path(next(iter(typeshed.__path__._path))) / "stdlib/ast.pyi"
# assert AST_TYPES_PYI.exists()
# Path("ast_pyi.py").write_text(
#     f"#Copy of {AST_TYPES_PYI}\n\nfrom __future__ import annotations\n{AST_TYPES_PYI.read_text()}".replace(
#         "from _typeshed", "# from _typeshed"
#     )
# )
import ast_pyi as ast

PATH = Path("src/trolskgen/ast_types.py")
FIELD_MAPS: dict[type[Any], dict[str, Any]] = {
    NoneType: {},
    str: {},
    int: {},
    object: {},
    bytes: {},
    float: {},
    complex: {},
}
FIELD_MAPS_3_14_ONWARDS: dict[type[Any], dict[str, Any]] = {}

for name, cls in ast.__dict__.items():
    try:
        if issubclass(cls, ast.AST):
            FIELD_MAPS[cls] = {}
    except TypeError:
        pass


def is_known_type(t: type[Any]) -> bool:
    if t in {True, False, Any}:
        return True
    if get_origin(t) in {Union, UnionType, list, Literal}:
        return all(is_known_type(t_inner) for t_inner in get_args(t))
    return t in FIELD_MAPS


# Pop deprecated
FIELD_MAPS.pop(ast.Num)
FIELD_MAPS.pop(ast.Str)
FIELD_MAPS.pop(ast.Bytes)
FIELD_MAPS.pop(ast.NameConstant)
FIELD_MAPS.pop(ast.Ellipsis)
FIELD_MAPS.pop(ast.slice)
FIELD_MAPS.pop(ast.ExtSlice)
FIELD_MAPS.pop(ast.Index)
FIELD_MAPS.pop(ast.AugLoad)
FIELD_MAPS.pop(ast.AugStore)
FIELD_MAPS.pop(ast.Param)
FIELD_MAPS.pop(ast.Suite)

IGNORE_FIELDS = {
    "ctx",
    "lineno",
    "col_offset",
    "end_lineno",
    "end_col_offset",
}

for cls in FIELD_MAPS:
    ts = get_type_hints(cls)
    for name, t in ts.items():
        if name.startswith("_") or name in IGNORE_FIELDS:
            continue
        assert is_known_type(t)
        if t is Any:
            t = object
        FIELD_MAPS[cls][name] = t

if sys.version_info >= (3, 14):
    FIELD_MAPS_3_14_ONWARDS[ast.Interpolation] = FIELD_MAPS.pop(ast.Interpolation)
    FIELD_MAPS_3_14_ONWARDS[ast.TemplateStr] = FIELD_MAPS.pop(ast.TemplateStr)

source = trolskgen.t(
    """
    import ast
    import sys
    from typing import Any, Literal

    FIELD_MAPS: dict[type[Any] | None, dict[str, Any]] = {FIELD_MAPS}
    if sys.version_info >= (3, 14):
        FIELD_MAPS |= {FIELD_MAPS_3_14_ONWARDS}
    """,
    FIELD_MAPS=FIELD_MAPS,
    FIELD_MAPS_3_14_ONWARDS=FIELD_MAPS_3_14_ONWARDS,
)
PATH.write_text(trolskgen.to_source(source).replace("ast_pyi", "ast").replace("NoneType", "None"))
subprocess.check_call(["ruff", "format", str(PATH)])

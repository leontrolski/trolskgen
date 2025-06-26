import ast
import subprocess
import sys
from pathlib import Path
from types import NoneType
from typing import Any, Union, get_args, get_origin, get_type_hints

import trolskgen

PATH = Path("src/trolskgen/ast_types.py")
FIELD_MAPS: dict[type[Any], dict[str, Any]] = {
    NoneType: {},
    str: {},
    int: {},
    object: {},
}
FIELD_MAPS_3_14_ONWARDS: dict[type[Any], dict[str, Any]] = {}

for name, cls in ast.__dict__.items():
    try:
        if issubclass(cls, ast.AST):
            FIELD_MAPS[cls] = {}
    except TypeError:
        pass


def is_known_type(t: type[Any]) -> bool:
    if get_origin(t) is Union or get_origin(t) is list:
        return all(is_known_type(t_inner) for t_inner in get_args(t))
    return t in FIELD_MAPS


for cls in FIELD_MAPS:
    ts = get_type_hints(cls)
    ts.pop("ctx", None)  # older Python versions do not have this
    for name, t in ts.items():
        assert is_known_type(t)
        FIELD_MAPS[cls][name] = t

if sys.version_info >= (3, 14):
    FIELD_MAPS_3_14_ONWARDS[ast.Interpolation] = FIELD_MAPS.pop(ast.Interpolation)
    FIELD_MAPS_3_14_ONWARDS[ast.TemplateStr] = FIELD_MAPS.pop(ast.TemplateStr)

source = trolskgen.t(
    """
    import ast
    import sys
    from types import NoneType
    from typing import Any

    FIELD_MAPS: dict[type[Any], dict[str, Any]] = {FIELD_MAPS}
    if sys.version_info >= (3, 14):
        FIELD_MAPS |= {FIELD_MAPS_3_14_ONWARDS}
    """,
    FIELD_MAPS=FIELD_MAPS,
    FIELD_MAPS_3_14_ONWARDS=FIELD_MAPS_3_14_ONWARDS,
)
PATH.write_text(trolskgen.to_source(source))
subprocess.check_call(["ruff", "format", str(PATH)])

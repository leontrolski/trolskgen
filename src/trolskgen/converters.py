from __future__ import annotations

import ast
import datetime as dt
import enum
import inspect
import textwrap
import zoneinfo
from dataclasses import MISSING, dataclass, fields, is_dataclass
from types import NoneType, UnionType
from typing import Annotated, Any, Literal, TypeVar, Union, cast, get_args, get_origin

from typing_extensions import TypeIs

from trolskgen import ast_types, core, templates

ASTValue = ast.AST | list[ast.stmt] | str
T = TypeVar("T", bound=ASTValue)


def converter_ast(o: Any, f: core.F) -> ast.AST | None:
    if not isinstance(o, ast.AST):
        return None
    return o


@core.upcast_expr
def converter_simple(o: Any, f: core.F) -> ast.AST | None:
    if isinstance(o, int | float | str | bool | NoneType):
        return ast.Constant(value=o)
    if isinstance(o, list):
        return ast.List(elts=[_downcast(ast.expr, f(e)) for e in o])
    if isinstance(o, tuple):
        return ast.Tuple(elts=[_downcast(ast.expr, f(e)) for e in o])
    if isinstance(o, dict):
        return ast.Dict(
            keys=[_downcast(ast.expr, f(k)) for k in o.keys()],
            values=[_downcast(ast.expr, f(v)) for v in o.values()],
        )
    if isinstance(o, set):
        return ast.Set(elts=[_downcast(ast.expr, f(e)) for e in o])
    return None


DONT_PREFIX_WITH_MODULE = {"builtins", "typing"}


@core.upcast_expr
def converter_types_and_functions(o: Any, f: core.F) -> ast.AST | None:
    if isinstance(o, type) or inspect.isfunction(o):
        module_name = o.__module__.split(".")[-1] + "."
        if o.__module__ in DONT_PREFIX_WITH_MODULE:
            module_name = ""
        return f(templates.t(module_name + o.__qualname__))
    return None


class FieldMissing: ...


FIELD_MISSING = FieldMissing()


@core.upcast_expr
def converter_common(o: Any, f: core.F) -> ast.AST | None:
    if o is dt.UTC:
        return f(templates.t("dt.UTC"))
    if isinstance(o, zoneinfo.ZoneInfo):
        return f(templates.t("zoneinfo.ZoneInfo({key})", key=o.key))
    if isinstance(o, dt.datetime):
        parts: list[int | ast.AST] = [o.year, o.month, o.day]
        if o.hour or o.minute or o.second or o.microsecond:
            parts.append(o.hour)
            parts.append(o.minute)
            parts.append(o.second)
        if o.microsecond:
            parts.append(o.microsecond)
        if o.tzinfo is not None:
            parts.append(f(templates.t("tzinfo={tzinfo}", tzinfo=o.tzinfo)))
        return f(templates.t("dt.datetime({parts:*})", parts=parts))
    if isinstance(o, dt.date):
        return f(templates.t("dt.date({year}, {month}, {day})", year=o.year, month=o.month, day=o.day))
    if isinstance(o, enum.Enum):
        return f(templates.t("{enum}.{name}", enum=type(o), name=templates.t(o.name)))
    if is_dataclass(o):
        args = list[ast.AST]()
        for field in fields(o):
            value = getattr(o, field.name, FIELD_MISSING)
            if value == field.default:
                continue
            if field.default_factory != MISSING and value == field.default_factory():
                continue
            args.append(f(templates.t("{key}={value}", key=templates.t(field.name), value=value)))
        return f(templates.t("{c}({args:*})", c=type(o), args=args))
    return None


@core.upcast_expr
def converter_pydantic(o: Any, f: core.F) -> ast.AST | None:
    import annotated_types
    import pydantic

    if isinstance(o, pydantic.BaseModel):
        args = list[ast.AST]()
        for name, field in o.__class__.model_fields.items():
            value = getattr(o, name, FIELD_MISSING)
            if value == field.default:
                continue
            if field.default_factory and value == field.default_factory():  # type: ignore[call-arg]
                continue
            args.append(f(templates.t("{key}={value}", key=templates.t(name), value=value)))
        return f(templates.t("{c}({args:*})", c=type(o), args=args))

    if isinstance(o, pydantic.fields.FieldInfo):
        args = list[ast.AST]()
        for metadata in o.metadata:
            if isinstance(metadata, annotated_types.MinLen):
                args.append(f(templates.t("min_length={min_length}", min_length=metadata.min_length)))
            elif isinstance(metadata, annotated_types.MaxLen):
                args.append(f(templates.t("max_length={max_length}", max_length=metadata.max_length)))
            elif hasattr(metadata, "pattern"):
                args.append(f(templates.t("pattern={pattern}", pattern=metadata.pattern)))
            else:
                raise NotImplementedError("Need to handle remainder of pydantic.Field")
        return f(templates.t("pydantic.Field({args:*})", args=args))

    return None


@core.upcast_expr
def converter_typeform(o: Any, f: core.F) -> ast.AST | None:
    if o is Annotated:
        return f(templates.t("Annotated"))
    if o is Literal:
        return f(templates.t("Literal"))
    if (origin := get_origin(o)) is not None:
        if origin is Union or origin is UnionType:
            a, b, *rest = get_args(o)
            union = f(templates.t("{a} | {b}", a=a, b=b))
            while rest:
                b, *rest = rest
                union = f(templates.t("{a} | {b}", a=union, b=f(b)))
            return union
        slice = [f(arg) for arg in get_args(o)]
        return f(templates.t("{a}[{b:*}]", a=origin, b=slice))

    return None


@core.upcast_expr
def converter_interface(o: Any, f: core.F) -> ast.AST | None:
    if not isinstance(o, core.ConvertInterface):
        return None

    return o.__trolskgen__(f)


def converter_template(o: Any, f: core.F) -> ast.AST | None:
    if not isinstance(o, templates.TemplateLike):
        return None

    o = templates.Template.from_templatelike(o)
    parts = list[str]()
    map = NameNodeMap()
    separator: str = ", "
    for part in o.parts:
        if isinstance(part, str):
            parts.append(part)
            separator = _trailing_indent(part)
        else:
            assert isinstance(part, templates.Interpolation)
            if part.format_spec == "*":
                if not isinstance(part.value, list):
                    raise core.TrolskgenError(f"Can only splat lists of values, not: {part.value!r}")
                v = [f(n) for n in part.value]
            else:
                v = [f(part.value)]

            for i, u in enumerate(v):
                if (named := _named(u)) is None:
                    name = map.insert(u)
                    parts.append(name)
                else:
                    parts.append(named.name)
                    if named.annotation is not None:
                        name = map.insert(named.annotation)
                        parts.append(f": {name}")
                    if named.value is not None:
                        name = map.insert(named.value)
                        parts.append(f" = {name}")
                if i != len(v) - 1:
                    parts.append(separator)

    node_template = textwrap.dedent("".join(parts)).strip()
    try:
        node = ast.parse(node_template)
    except SyntaxError as e:
        raise core.TrolskgenError(f"SyntaxError with template:\n\n{node_template}") from e

    _ast_replace(node, map)
    assert not map.map
    return node


# `converter_template` replacement helpers


class NameNodeMap:
    def __init__(self) -> None:
        self.i = -1
        self.map = dict[str, ast.AST]()

    def insert(self, v: ast.AST) -> str:
        self.i += 1
        name = f"__tg_{self.i}"
        self.map[name] = v
        return name

    def pop(self, v: ast.AST | str) -> ast.AST | None:
        if isinstance(v, ast.Expr):
            v = v.value
        if isinstance(v, ast.Name):
            v = v.id
        if isinstance(v, str) and v in self.map:
            return self.map.pop(v)
        return None


def _is_instance(v: ASTValue, t: type[T]) -> TypeIs[T]:
    """`isinstance`, but handles `t = list[T], t = A | B`"""
    if get_origin(t) is list:
        [t_inner] = get_args(t)
        return isinstance(v, list) and all(_is_instance(u, t_inner) for u in v)
    if get_origin(t) is Union:
        return any(_is_instance(v, t_inner) for t_inner in get_args(t))

    return isinstance(v, t)


def _downcast(t: type[T], v: ASTValue) -> T:
    """Keep removing layers of AST until hopefully, `_is_instance(v, t)`."""
    v_original = v
    while not _is_instance(v, t):
        if isinstance(v, list) and get_origin(t) is list:
            [r] = get_args(t)
            return cast(T, [_downcast(r, u) for u in v])
        if isinstance(v, ast.Module):
            v = v.body
        elif isinstance(v, list) and len(v) == 1:
            v = v[0]
        elif isinstance(v, ast.Expr):
            v = v.value
        elif isinstance(v, ast.Name):
            v = v.id
        else:
            raise core.TrolskgenError(f"Cannot convert {v_original!r} to {t!r}, got as far as {v!r}")
    return v


@dataclass
class _Named:
    name: str
    annotation: ast.expr | None
    value: ast.expr | None


def _named(v: ast.AST) -> _Named | None:
    """Convert eg. `a: int = 1` to `Named("a", int, 1)`."""
    if isinstance(v, ast.Module) and len(v.body) == 1:
        v = v.body[0]
    if isinstance(v, ast.Assign) and len(v.targets) == 1 and isinstance(v.targets[0], ast.Name):
        return _Named(v.targets[0].id, None, v.value)
    if isinstance(v, ast.AnnAssign) and isinstance(v.target, ast.Name):
        return _Named(v.target.id, v.annotation, v.value)
    return None


def _trailing_indent(part: str) -> str:
    """Get the trailing indent of a part.

    If previous to the newline, there was a comma, assume we're in a
    comma separated list.
    """
    lines = part.splitlines()
    try:
        trailing_comma = lines[-2][-1] == ","
    except IndexError:
        trailing_comma = False
    if all(c == " " for c in lines[-1]) and not trailing_comma:
        return "\n" + lines[-1]
    return ", "


def _ast_replace(node: ast.AST, map: NameNodeMap) -> None:
    """Traverse the AST, replacing nodes with items from the `map`."""
    type_map = ast_types.FIELD_MAPS.get(type(node))
    if not type_map:
        return

    for name, t in type_map.items():
        v = getattr(node, name)

        if (interpolation := map.pop(v)) is not None:
            v = interpolation
        elif isinstance(v, list):
            for i, u in enumerate(v):
                if (interpolation := map.pop(u)) is not None:
                    v[i] = interpolation

        v = _downcast(t, v)
        setattr(node, name, v)

        # recurse
        if isinstance(v, list):
            for u in v:
                _ast_replace(u, map)
        else:
            _ast_replace(v, map)

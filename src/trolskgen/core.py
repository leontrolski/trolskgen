from __future__ import annotations

import ast
from contextvars import ContextVar
import subprocess
from dataclasses import dataclass, field
from functools import cache, partial
from typing import Any, Callable, Union


class TrolskgenError(RuntimeError): ...


F = Callable[[Any], ast.Module]
Converter = Callable[[Any, F], ast.Module | ast.expr | None]


@cache
def safe_converter_pydantic() -> Converter | None:
    from trolskgen import converters

    try:
        import pydantic  # noqa: F401

        return converters.converter_pydantic
    except ImportError:
        return None


def default_converters() -> list[Converter]:
    from trolskgen import converters

    out: list[Converter] = [
        converters.converter_ast,
        converters.converter_template,
        converters.converter_interface,
        converters.converter_simple,
        converters.converter_types_and_functions,
        converters.converter_typeform,
        converters.converter_common,
    ]
    if (converter_pydantic := safe_converter_pydantic()) is not None:
        out.append(converter_pydantic)
    return out


@dataclass(kw_only=True)
class Config:
    converters: list[Converter] = field(default_factory=default_converters)

    def prepend_converter(self, converter: Converter, *, before: Converter | None = None) -> Config:
        out = Config(converters=[*self.converters])
        i = 0
        if before is not None:
            for i, other in enumerate(out.converters):
                if other is before:
                    break
            else:
                raise TrolskgenError(f"Couldn't find converter: {before}")
        out.converters.insert(i, converter)
        return out


GLOBAL_CONFIG: ContextVar[Config] = ContextVar("GLOBAL_CONFIG", default=Config())


class Module(ast.Module):
    """ast.Module with pprint methods"""

    def to_source(self) -> str:
        return ast.unparse(self)

    def pprint(self) -> None:
        print(self.to_source())

    def __repr__(self) -> str:
        return f"<ast.Module {self.to_source()!r}>"

    def __or__(self, value: object) -> type[object]:
        return Union[self, value]  # type: ignore[return-value]


def _upcast(node: ast.Module | ast.expr) -> Module:
    if isinstance(node, ast.expr):
        return Module(body=[ast.Expr(value=node)], type_ignores=[])

    return Module(body=node.body, type_ignores=node.type_ignores)


def to_ast(o: object, *, config: Config | None = None) -> Module:
    if config is None:
        config = GLOBAL_CONFIG.get()
    f = partial(to_ast, config=config)
    for converter in config.converters:
        if (node := converter(o, f)) is not None:
            return _upcast(node)

    raise TrolskgenError(f"No converter matchers: {o!r}")


def e(s: str, **kwargs: object) -> Module:
    """Like `trolskgen.t`, but eagerly converts to `ast`."""
    from trolskgen import templates

    template = templates.Template.from_str(s, **kwargs)
    return to_ast(template, config=GLOBAL_CONFIG.get())


def sh(cmd: list[str], stdin: str) -> str:
    result = subprocess.run(
        cmd,
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return result.stdout


def to_source(
    o: object,
    *,
    config: Config | None = None,
    ruff_format: bool = False,
    ruff_line_length: int = -1,
) -> str:
    source = to_ast(o, config=config).to_source()
    if ruff_format:
        line_length_args = [] if ruff_line_length == -1 else ["--line-length", str(ruff_line_length)]
        source = sh(["ruff", "format", "-"] + line_length_args, source)
        source = sh(["ruff", "check", "-e", "--fix", "-"], source)
        source = sh(["ruff", "check", "-e", "--select", "I", "--fix", "-"], source)
    return source

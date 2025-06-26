from __future__ import annotations

import sys
from dataclasses import dataclass
from string import Formatter

if sys.version_info >= (3, 14):
    from string import templatelib
from typing import Any, Self


class TemplateError(RuntimeError): ...


@dataclass
class Interpolation:
    value: Any
    expression: str
    format_spec: str | None


@dataclass
class Template:
    parts: list[str | Interpolation]

    @classmethod
    def from_str(cls, s: str, **kwargs: Any) -> Self:
        out = cls([])
        for literal_text, field_name, format_spec, _conversion in Formatter().parse(s):
            if literal_text:
                out.parts.append(literal_text)
            if field_name is not None:
                try:
                    value = kwargs[field_name]
                except KeyError:
                    raise TemplateError(f"Kwargs missing key: {field_name}\n\n{s}")
                out.parts.append(
                    Interpolation(
                        value=value,
                        expression=field_name,
                        format_spec=format_spec,
                    )
                )
        return out

    if sys.version_info >= (3, 14):

        @classmethod
        def from_templatelike(cls, t: str | templatelib.Template | Self) -> Self:
            if isinstance(t, str):
                return Template.from_str(t)
            if isinstance(t, Template):
                return t
            assert isinstance(t, templatelib.Template)
            out = Template([])
            for part in t:
                if isinstance(part, str):
                    out.parts.append(part)
                else:
                    assert isinstance(part, templatelib.Interpolation)
                    out.parts.append(
                        Interpolation(
                            value=part.value,
                            expression=part.expression,
                            format_spec=part.format_spec,
                        )
                    )
            return out
    else:

        @classmethod
        def from_templatelike(cls, t: str | Self) -> Self:
            if isinstance(t, str):
                return cls.from_str(t)
            assert isinstance(t, cls)
            return t


if sys.version_info >= (3, 14):
    TemplateLike = Template | templatelib.Template
else:
    TemplateLike = Template

t = Template.from_str

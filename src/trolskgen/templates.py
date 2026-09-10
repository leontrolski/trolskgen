from __future__ import annotations

import sys
from dataclasses import dataclass
from string import Formatter

if sys.version_info >= (3, 14):
    from string import templatelib
from typing import Self, Union


class TemplateError(RuntimeError): ...


@dataclass(frozen=True)
class Interpolation:
    value: object
    expression: str
    format_spec: str | None


class Composite(tuple[object]): ...


@dataclass(frozen=True)
class Template:
    parts: tuple[str | Interpolation, ...]

    def __or__(self, value: object) -> type[object]:
        return Union[self, value]  # type: ignore[return-value]

    @classmethod
    def from_str(cls, s: str, **kwargs: object) -> Self:
        parts = list[str | Interpolation]()
        for literal_text, field_name, format_spec, _conversion in Formatter().parse(s):
            if literal_text:
                parts.append(literal_text)
            if field_name is not None:
                value: object
                if "," in field_name:
                    for sub_field_name in field_name.split(","):
                        if sub_field_name not in kwargs:
                            raise TemplateError(f"Kwargs missing key: {field_name}\n\n{s}")
                    value = Composite(kwargs[sub_field_name] for sub_field_name in field_name.split(","))
                else:
                    try:
                        value = kwargs[field_name]
                    except KeyError:
                        raise TemplateError(f"Kwargs missing key: {field_name}\n\n{s}")
                parts.append(
                    Interpolation(
                        value=value,
                        expression=field_name,
                        format_spec=format_spec,
                    )
                )
        return cls(tuple(parts))

    if sys.version_info >= (3, 14):

        @classmethod
        def from_templatelike(cls, t: str | templatelib.Template | Self) -> Self:
            if isinstance(t, str):
                return cls.from_str(t)
            if isinstance(t, Template):
                return t
            assert isinstance(t, templatelib.Template)
            parts = list[str | Interpolation]()
            for part in t:
                if isinstance(part, str):
                    parts.append(part)
                else:
                    assert isinstance(part, templatelib.Interpolation)
                    parts.append(
                        Interpolation(
                            value=part.value,
                            expression=part.expression,
                            format_spec=part.format_spec,
                        )
                    )
            return cls(tuple(parts))
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

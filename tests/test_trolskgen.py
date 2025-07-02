import ast
import datetime as dt
import textwrap
import zoneinfo
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

import pydantic
import pytest

import trolskgen
from tests.nested import MyEnum
from trolskgen import t


def _eq(a: str, b: str) -> None:
    assert a == textwrap.dedent(b).strip()


def test_config() -> None:
    def _1(o: Any, f: trolskgen.F) -> ast.AST | None:
        return None

    def _2(o: Any, f: trolskgen.F) -> ast.AST | None:
        return None

    def _3(o: Any, f: trolskgen.F) -> ast.AST | None:
        return None

    c = trolskgen.Config(converters=[])
    c = c.prepend_converter(_2)
    c = c.prepend_converter(_1)
    assert c == trolskgen.Config(converters=[_1, _2])

    c = c.prepend_converter(_3, before=_1)


# if sys.version_info >= (3, 14):
#     def test_new_template_strings() -> None:
#         name = "World"
#         template = t"Hello {name:I'm a big long [weird] string! }"
#         interpolation = Interpolation(
#             value="World",
#             expression="name",
#             format_spec="I'm a big long [weird] string! ",
#         )
#         assert template.interpolations[0].value == interpolation.value
#         assert template.interpolations[0].expression == interpolation.expression
#         assert template.interpolations[0].format_spec == interpolation.format_spec
# F
#     def test_build_class_simple_new_skool_templates() -> None:
#         name = "Foo"
#         cls = t"""
#             class {name}:
#                 ...
#         """
#         _eq(
#             trolskgen.to_node(cls),
#             """
#             class Foo:
#                 ...
#             """,
#         )


def test_error_missing_paren() -> None:
    name = t("Foo")
    bases = [int, list]
    field_name = t("bar")
    fields = [
        t("foo: {int}", int=int),
        t("{field_name}: str", field_name=field_name),
    ]
    cls = t(
        """
        class {name}({bases}:
            {fields}
        """,
        name=name,
        bases=bases,
        fields=fields,
    )
    with pytest.raises(trolskgen.TrolskgenError):
        trolskgen.to_source(cls)


def test_build_field() -> None:
    _eq(
        trolskgen.to_source(t("foo: {int}", int=int)),
        "foo: int",
    )


def test_build_class_simple() -> None:
    name = t("Foo")
    cls = t(
        """
        class {name}:
            ...
        """,
        name=name,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo:
            ...
        """,
    )

    name_ = "Foo"
    cls = t(
        """
        class {name_}:
            ...
        """,
        name_=name_,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo:
            ...
        """,
    )


def test_build_class_one_base_class() -> None:
    base = int
    cls = t(
        """
        class Foo({base}):
            ...
        """,
        base=base,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo(int):
            ...
        """,
    )


def test_build_class_two_base_classes() -> None:
    bases = [int, str]
    cls = t(
        """
        class Foo({bases:*}):
            ...
        """,
        bases=bases,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo(int, str):
            ...
        """,
    )


def test_build_class() -> None:
    name = t("Foo")
    bases = [int, list]
    field_name = t("bar")
    fields = [
        t("foo: {int}", int=int),
        t("{field_name}: str", field_name=field_name),
    ]
    cls = t(
        """
        class {name}({bases:*}):
            {fields:*}
        """,
        name=name,
        bases=bases,
        fields=fields,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo(int, list):
            foo: int
            bar: str
        """,
    )


def test_build_class_docstring() -> None:
    base = int
    cls = t(
        """
        class Foo({base}):
            {docstring}
        """,
        base=base,
        docstring="Some.\n\n    Mutliline\n    docstring\n    ",
    )
    _eq(
        trolskgen.to_source(cls),
        '''
        class Foo(int):
            """Some.

            Mutliline
            docstring
            """
        ''',
    )


def test_build_union() -> None:
    a = int
    b = str
    code = t(
        """
        Either = {a} | {b}
        """,
        a=a,
        b=b,
    )
    _eq(
        trolskgen.to_source(code),
        """
        Either = int | str
        """,
    )

    a_or_b_or_c = int | str | float
    code = t(
        """
        Either = {a_or_b_or_c}
        """,
        a_or_b_or_c=a_or_b_or_c,
    )
    _eq(
        trolskgen.to_source(code),
        """
        Either = int | str | float
        """,
    )


def test_build_annotated() -> None:
    ann = Annotated[int | str, 42]
    code = t(
        """
        Either = {ann}
        """,
        ann=ann,
    )
    _eq(
        trolskgen.to_source(code),
        """
        Either = Annotated[int | str, 42]
        """,
    )


def test_splat() -> None:
    code = t("[{a:*}, float]", a=[int, int])
    _eq(
        trolskgen.to_source(code),
        "[int, int, float]",
    )

    code = t("list[str, {a:*}, float]", a=[int, int])
    _eq(
        trolskgen.to_source(code),
        "list[str, int, int, float]",
    )

    code = t("list[{a:*}]", a=[int, int])
    _eq(
        trolskgen.to_source(code),
        "list[int, int]",
    )


def test_build_custom_int() -> None:
    def custom_int_converter(o: Any, f: trolskgen.F) -> ast.AST | None:
        if not isinstance(o, int):
            return None
        return f(t(f"{o - 1} + 1"))

    c = trolskgen.Config().prepend_converter(custom_int_converter)
    _eq(
        trolskgen.to_source([6, 9], config=c),
        "[5 + 1, 8 + 1]",
    )


class MyInterfaceClass:
    def __trolskgen__(self, f: trolskgen.F) -> ast.AST:
        return f(t("MyInterfaceClass({values:*})", values=[1, 2, 3]))


def test_convert_interface() -> None:
    interfacey: trolskgen.ConvertInterface = MyInterfaceClass()
    _eq(
        trolskgen.to_source(interfacey),
        "MyInterfaceClass(1, 2, 3)",
    )


def test_build_function() -> None:
    name = t("f")
    a = int
    y = t("y: str")
    z = t("z: int = 1")
    func = t(
        """
        def {name}(x: {a}, {y}, {z}):
            ...
        """,
        name=name,
        a=a,
        y=y,
        z=z,
    )
    _eq(
        trolskgen.to_source(func),
        """
        def f(x: int, y: str, z: int=1):
            ...
        """,
    )

    b = t("a = 1")
    func = t(
        """
        def {name}(x: {a}, {y}, {b}):
            ...
        """,
        name=name,
        a=a,
        y=y,
        b=b,
    )
    _eq(
        trolskgen.to_source(func),
        """
        def f(x: int, y: str, a=1):
            ...
        """,
    )

    func = t(
        """
        def {name}(x: {a}, {args:*}):
            ...
        """,
        name=name,
        a=a,
        args=[y, z],
    )
    _eq(
        trolskgen.to_source(func),
        """
        def f(x: int, y: str, z: int=1):
            ...
        """,
    )
    func = t(
        """
        def {name}(
            x: {a},
            {args:*},
        ):
            ...
        """,
        name=name,
        a=a,
        args=[y, z],
    )
    _eq(
        trolskgen.to_source(func),
        """
        def f(x: int, y: str, z: int=1):
            ...
        """,
    )


def test_nested_lambda() -> None:
    name = t("x")
    list_ = t(
        """
        [lambda {name}: 1]
        """,
        name=name,
    )
    _eq(
        trolskgen.to_source(list_),
        """
        [lambda x: 1]
        """,
    )


def test_decorator() -> None:
    name = t("decorator()")
    list_ = t(
        """
        @{name}
        def f():
            ...
        """,
        name=name,
    )
    _eq(
        trolskgen.to_source(list_),
        """
        @decorator()
        def f():
            ...
        """,
    )


def test_methods() -> None:
    f = t(
        """
        def f(self):
            ...
        """
    )
    g = t(
        """
        def g(self):
            ...
        """
    )
    cls = t(
        """
        class Foo:
            {f}
            {g}
        """,
        f=f,
        g=g,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo:

            def f(self):
                ...

            def g(self):
                ...
        """,
    )


def test_methods_and_annotation() -> None:
    ann = t("""x: {a}""", a=int | str)
    g = t(
        """
        def g():
            ...
        """
    )
    f = t(
        """
        def f(self):
            {g}
        """,
        g=g,
    )
    ann_and_f = [ann, f]

    cls = t(
        """
        class Foo:
            {ann_and_f:*}
        """,
        ann_and_f=ann_and_f,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class Foo:
            x: int | str

            def f(self):

                def g():
                    ...
        """,
    )


def f() -> None: ...


class Foo:
    def f(self) -> None: ...


@dataclass
class Bar:
    a: int
    b: list[int] = field(default_factory=list)
    c: int = 1
    d: list[int] = field(default_factory=list)


class Qux(pydantic.BaseModel):
    a: int
    b: list[int] = []
    c: int = 1
    d: list[int] = []


def test_more_reprs() -> None:
    _eq(
        trolskgen.to_source(f),
        "test_trolskgen.f",
    )
    _eq(
        trolskgen.to_source(Foo.f),
        "test_trolskgen.Foo.f",
    )
    _eq(
        trolskgen.to_source(dt.date(2022, 1, 23)),
        "dt.date(2022, 1, 23)",
    )
    _eq(
        trolskgen.to_source(dt.datetime(2022, 1, 23)),
        "dt.datetime(2022, 1, 23)",
    )
    _eq(
        trolskgen.to_source(dt.datetime(2022, 1, 23, 1)),
        "dt.datetime(2022, 1, 23, 1, 0, 0)",
    )
    _eq(
        trolskgen.to_source(dt.datetime(2022, 1, 23, 1, 2, 3, 12345)),
        "dt.datetime(2022, 1, 23, 1, 2, 3, 12345)",
    )
    _eq(
        trolskgen.to_source(dt.datetime(2022, 1, 23, tzinfo=dt.UTC)),
        "dt.datetime(2022, 1, 23, tzinfo=dt.UTC)",
    )
    _eq(
        trolskgen.to_source(dt.datetime(2022, 1, 23, tzinfo=zoneinfo.ZoneInfo("Europe/London"))),
        "dt.datetime(2022, 1, 23, tzinfo=zoneinfo.ZoneInfo('Europe/London'))",
    )
    _eq(
        trolskgen.to_source(MyEnum.FOO),
        "nested.MyEnum.FOO",
    )
    _eq(
        trolskgen.to_source(Bar(a=1, b=[2])),
        "test_trolskgen.Bar(a=1, b=[2])",
    )
    _eq(
        trolskgen.to_source(Qux(a=1, b=[2])),
        "test_trolskgen.Qux(a=1, b=[2])",
    )
    _eq(
        trolskgen.to_source(Literal[1, 2]),
        "Literal[1, 2]",
    )
    _eq(
        trolskgen.to_source(pydantic.Field(max_length=1, pattern="x")),
        "pydantic.Field(max_length=1, pattern='x')",
    )
    _eq(
        trolskgen.to_source(()),
        "()",
    )


def test_used_in_readme() -> None:
    name = t("f")
    func = t(
        """
        def {name}():
            ...
        """,
        name=name,
    )
    _eq(
        trolskgen.to_source(func),
        """
        def f():
            ...
        """,
    )
    # ast.Module(
    #     body=[
    #         ast.FunctionDef(
    #             name="f",
    #             args=ast.arguments(...),
    #             body=[ast.Expr(value=ast.Constant(value=Ellipsis))],
    #             decorator_list=[],
    #             type_params=[],
    #         )
    #     ],
    # )

    name = t("MySpecialClass")
    bases = [int, list]
    field_name = t("d")
    fields = [
        t(
            "a: {type_}",
            type_=str,
        ),
        t(
            "{field_name}: dt.date = {default}",
            field_name=field_name,
            default=dt.date(2000, 1, 1),
        ),
    ]
    method = t(
        """
        def inc(self) -> None:
            self.{field_name} += dt.timedelta(days=1)
        """,
        field_name=field_name,
    )
    cls = t(
        """
        class {name}({bases:*}, float):
            {fields:*}
            {method}
        """,
        name=name,
        bases=bases,
        fields=fields,
        method=method,
    )
    _eq(
        trolskgen.to_source(cls),
        """
        class MySpecialClass(int, list, float):
            a: str
            d: dt.date = dt.date(2000, 1, 1)

            def inc(self) -> None:
                self.d += dt.timedelta(days=1)
        """,
    )

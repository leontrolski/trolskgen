# `trolskgen`

Ergonomic codegen for Python - `pip install trolskgen`.

<details>
    <summary><em>Note on Python 3.14 template strings.</em></summary>

<br>

From Python 3.14 upwards, there are [template strings](https://peps.python.org/pep-0750/), these make `trolskgen` significantly more succinct.

Where previously you'd do:

```python
name = t("f")
func = t(
    """
    def {name}():
        ...
    """,
    name=name,
)
trolskgen.to_source(func)
```

As of Python 3.14, you can do:

```python
name = t"f"
func =  t"""
    def {name}():
        ...
"""
trolskgen.to_source(func)
```

There are some `if sys.version_info >= (3, 14)` flags around, but it _should_ just work come release date.

<hr>

</details>

`trolskgen` lets you easily build and compose `ast.AST` trees, and thereby easily generate source code. It doesn't handle any formatting concerns, just [`ruff format`](https://github.com/astral-sh/ruff) it afterwards. If you want comments, sorry, instead use a docstring or some `Annotated[]` wizardry.

Quick example:

```python
import trolskgen
from trolskgen import t

name = t("f")
func = t(
    """
    def {name}():
        ...
    """,
    name=name,
)
trolskgen.to_source(func)
trolskgen.to_ast(func)
```

Gives you the source `str`:

```python
def f():
    ...
```

And the `ast.AST`:

```python
ast.Module(
    body=[
        ast.FunctionDef(
            name="f",
            args=ast.arguments(...),
            body=[ast.Expr(value=ast.Constant(value=Ellipsis))],
            decorator_list=[],
            type_params=[],
        )
    ],
)
```

<hr>

A more complete example:

```python
import datetime as dt

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
my_special_class_source = t(
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

trolskgen.to_source(my_special_class_source)
```

Gives you the source `str`:

```python
class MySpecialClass(int, list, float):
    a: str
    d: dt.date = dt.date(2000, 1, 1)

    def inc(self) -> None:
        self.d += dt.timedelta(days=1)
```

# API

| Building templates |
|---|
| `trolskgen.t(s: str, **kwargs: Any) -> trolskgen.templates.Template` |

Creates source templates. If you use the format string `:*`, it will splat in place - see above: `{bases:*}`, `{fields:*}`

_This is redundant as of Python 3.14 - see above._

| Converting to AST/source|
|---|
| `trolskgen.to_ast(o: Any, *, config: Config) -> ast.AST` |
| `trolskgen.to_source(o: Any, *, config: Config) -> str` |

Try to convert `o` into an `ast.AST`/`str` representation.

The following are special cases for the value of `o`:
- `ast.AST` nodes - these just get passed straight back out.
- `trolskgen.templates.Template` or `string.templatelib.Template` - these get parsed as Python code.

`trolskgen` will generate sensible ASTs, for the following types:

- `None`
- `int`
- `float`
- `str`
- `bool`
- `list`
- `tuple`
- `dict`
- `set`
- `classes`
- `functions`
- `dt.datetime`
- `dt.date`
- `enum.Enum`
- `dataclass`
- `Annotated`, `T | U`, etc.
- `pydantic.BaseModel`

_Note that in conjunction with `ruff`, we have a decent pretty printer that you can use for test diffs etc._

We can add our own classes/overrides using:

| Configuring/Overriding |
|---|
| `trolskgen.ConvertInterface` |
| `trolskgen.Converter` |
| `trolskgen.Config` |
| `trolskgen.Config().prepend_converter(converter: Converter, *, before: Converter \| None) -> Config` |

If you own the class, you can just add a `__trolskgen__` method that satisfies `trolskgen.ConvertInterface`.

For example:

```python
class MyInterfaceClass:
    def __trolskgen__(self, f: trolskgen.F) -> ast.AST:
        return f(t("MyInterfaceClass({values:*})", values=[1, 2, 3]))

trolskgen.to_source(MyInterfaceClass()) == "MyInterfaceClass(1, 2, 3)"
```

Note that we use `f` to recursively call `trolskgen.to_ast(...)` while preserving the current `Config`.

<hr>

If you don't own the class, you can build a `trolskgen.Config` with a custom `Converter` function.

For example, if you for some reason wanted to render all ints in the form `x + 1`, you could:

```python
def custom_int_converter(o: Any, f: trolskgen.F) -> ast.AST | None:
    if not isinstance(o, int):
        return None
    return f(t(f"{o - 1} + 1"))

config = trolskgen.Config().prepend_converter(custom_int_converter)
trolskgen.to_source([6, 9], config=config) == "[5 + 1, 8 + 1]"
```

# Development

```
uv pip install -e '.[dev]'
mypy .
pytest -vv
uv pip install build twine
python -m build
twine check dist/*
twine upload dist/*
```

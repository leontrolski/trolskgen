# `trolskgen`

```shell
pip install trolskgen
```

Easily _compose_ types/values/string-templates/AST-nodes, then convert to source.

<table>
    <thead>
        <tr>
            <th>Codgen</th>
            <th><code>.to_source()</code></th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><pre><code>trolskgen.e(
    "foo: {t}",
    t=trolskgen.e("some.Class") | int,
)</pre></code></td>
            <td><pre><code>foo: some.Class | int</pre></code></td>
        </tr>
        <tr>
            <td><pre><code>trolskgen.e(
    """
    class {name}({bases:*}):
        {fields:*}
    """,
    name="Foo",
    bases=[int, list],
    fields=[
        trolskgen.e("foo: {int}", int=int),
        trolskgen.e("{field_name}: str", field_name="bar"),
    ],
)</pre></code></td>
            <td><pre><code>class Foo(int, list):
    foo: int
    bar: str</pre></code></td>
        </tr>
        <tr>
            <td><pre><code>trolskgen.e(
    "f({args,kwargs:*})",
    args=[],
    kwargs={"a": 1, "b": [2, 3]},
)</pre></code></td>
            <td><pre><code>f(a=1, b=[2, 3])</pre></code></td>
        </tr>
    </tbody>
</table>


If you want formatting, run [`ruff format`](https://github.com/astral-sh/ruff) over the output. If you want comments, sorry, instead use a docstring, some `Annotated[]` wizardry, or fork this library to use [LibCST](https://github.com/Instagram/LibCST).

[Blog post](https://leontrolski.github.io/trolskgen.html) with a motivating example.


# API

| Building templates |
|---|
| `trolskgen.t(s: str, **kwargs: object) -> trolskgen.templates.Template` |
| `trolskgen.e(s: str, **kwargs: object) -> trolskgen.ASTModule` |

`trolskgen.t` creates source templates. If you use the format string `:*`, it will splat in place - see above: `{bases:*}`, `{fields:*}`, `{args,kwargs:*}`

<details>
    <summary><em>Note on Python 3.14 template strings.</em></summary>

<br>

From Python 3.14 upwards, there are [template strings](https://peps.python.org/pep-0750/), these make `trolskgen` significantly more succinct.

Where previously you'd do:

```python
name = trolskgen.t("f")
func = trolskgen.t(
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
func = t"""
    def {name}():
        ...
"""
trolskgen.to_source(func)
```

There are some `if sys.version_info >= (3, 14)` flags around, but it _should_ just work come release date.

<hr>

</details>

`e` is for "eager" - this might be preferable to use, otherwise error messages can become pretty inscrutable.

<br>
<br>

| Converting to AST/source|
|---|
| `trolskgen.to_ast(o: object, *, config: Config) -> trolskgen.ASTModule` |
| `trolskgen.to_source(o: object, *, config: Config, ruff_format: bool, ruff_line_length: int) -> str` |

Lower level functions to convert `o` into an `ast.AST`/`str` representation.

The following are special cases for the value of `o`:
- `ast.Module | ast.expr` nodes - these just get passed straight back out.
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

If you have `ruff` installed, you can call with `ruff_format=True`.


<br>
<br>

| Configuring/Overriding |
|---|
| `__trolskgen__` |
| `__trolskgen_cls__` |
| `trolskgen.Converter` |
| `trolskgen.Config` |
| `trolskgen.Config().prepend_converter(converter: Converter, *, before: Converter \| None) -> Config` |
| `trolskgen.GLOBAL_CONFIG` |

If you own the class, you can just add a `__trolskgen__` method:

For example:

```python
class MyInterfaceClass:
    def __trolskgen__(self, f: trolskgen.F) -> ast.Module:
        return f(trolskgen.t("MyInterfaceClass({values:*})", values=[1, 2, 3]))


trolskgen.to_source(MyInterfaceClass()) == "MyInterfaceClass(1, 2, 3)"
```

You can also add a `__trolskgen_cls__` `@classmethod`:

```python
@dataclass
class MyJustName:
    a: str

    @classmethod
    def __trolskgen_cls__(cls, f: trolskgen.F) -> ast.Module:
        return f(trolskgen.t("Foo"))


trolskgen.to_source(MyJustName("bar")) == "Foo(a='bar')"
```

Note that we use `f` to recursively call `trolskgen.to_ast(...)` while preserving the current `Config`.

<hr>

If you don't own the class, you can build a `trolskgen.Config` with a custom `Converter` function.

For example, if you for some reason wanted to render all ints in the form `x + 1`, you could:

```python
def custom_int_converter(o: object, f: trolskgen.F) -> ast.Module | None:
    if not isinstance(o, int):
        return None
    return f(trolskgen.t(f"{o - 1} + 1"))


config = trolskgen.Config().prepend_converter(custom_int_converter)
trolskgen.to_source([6, 9], config=config) == "[5 + 1, 8 + 1]"
```

You can also set a global `trolskgen.GLOBAL_CONFIG` [`ContextVar`](https://docs.python.org/3/library/contextvars.html).

```python
with trolskgen.GLOBAL_CONFIG.set(config):
    trolskgen.to_source([6, 9]) == "[5 + 1, 8 + 1]"
```

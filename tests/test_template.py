from trolskgen import templates


def test_templates() -> None:
    assert templates.Template.from_templatelike("Hello") == templates.Template(["Hello"])
    this = "THIS"
    world = "WORLD"
    expected = templates.Template(
        [
            "Hello ",
            templates.Interpolation(
                value="THIS",
                expression="this",
                format_spec="foo",
            ),
            templates.Interpolation(
                value="WORLD",
                expression="world",
                format_spec="",
            ),
        ]
    )
    assert templates.Template.from_str("Hello {this:foo}{world}", this=this, world=world) == expected
    assert templates.Template.from_templatelike(expected) == expected

    # if sys.version_info >= (3, 14):
    #     assert templates.Template.from_any(t"Hello {this:foo}{world}") == expected

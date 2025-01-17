"""
Tests focusing on the Component class.
For tests focusing on the `component` tag, see `test_templatetags_component.py`
"""

from typing import Dict, Tuple, TypedDict, no_type_check

from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.template import Context, RequestContext, Template, TemplateSyntaxError

from django_components import Component, registry, types
from django_components.slots import SlotRef

from .django_test_setup import setup_test_config
from .testutils import BaseTestCase, parametrize_context_behavior

setup_test_config({"autodiscover": False})


class ComponentTest(BaseTestCase):
    class ParentComponent(Component):
        template: types.django_html = """
            {% load component_tags %}
            <div>
                <h1>Parent content</h1>
                {% component name="variable_display" shadowing_variable='override' new_variable='unique_val' %}
                {% endcomponent %}
            </div>
            <div>
                {% slot 'content' %}
                    <h2>Slot content</h2>
                    {% component name="variable_display" shadowing_variable='slot_default_override' new_variable='slot_default_unique' %}
                    {% endcomponent %}
                {% endslot %}
            </div>
        """  # noqa

        def get_context_data(self):
            return {"shadowing_variable": "NOT SHADOWED"}

    class VariableDisplay(Component):
        template: types.django_html = """
            {% load component_tags %}
            <h1>Shadowing variable = {{ shadowing_variable }}</h1>
            <h1>Uniquely named variable = {{ unique_variable }}</h1>
        """

        def get_context_data(self, shadowing_variable=None, new_variable=None):
            context = {}
            if shadowing_variable is not None:
                context["shadowing_variable"] = shadowing_variable
            if new_variable is not None:
                context["unique_variable"] = new_variable
            return context

    def setUp(self):
        super().setUp()
        registry.register(name="parent_component", component=self.ParentComponent)
        registry.register(name="variable_display", component=self.VariableDisplay)

    @parametrize_context_behavior(["django", "isolated"])
    def test_empty_component(self):
        class EmptyComponent(Component):
            pass

        with self.assertRaises(ImproperlyConfigured):
            EmptyComponent("empty_component").get_template(Context({}))

    @parametrize_context_behavior(["django", "isolated"])
    def test_template_string_static_inlined(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                Variable: <strong>{{ variable }}</strong>
            """

            def get_context_data(self, variable=None):
                return {
                    "variable": variable,
                }

            class Media:
                css = "style.css"
                js = "script.js"

        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_template_string_dynamic(self):
        class SimpleComponent(Component):
            def get_template_string(self, context):
                content: types.django_html = """
                    Variable: <strong>{{ variable }}</strong>
                """
                return content

            def get_context_data(self, variable=None):
                return {
                    "variable": variable,
                }

            class Media:
                css = "style.css"
                js = "script.js"

        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_template_name_static(self):
        class SimpleComponent(Component):
            template_name = "simple_template.html"

            def get_context_data(self, variable=None):
                return {
                    "variable": variable,
                }

            class Media:
                css = "style.css"
                js = "script.js"

        rendered = SimpleComponent.render(kwargs={"variable": "test"})
        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_template_name_dynamic(self):
        class SvgComponent(Component):
            def get_context_data(self, name, css_class="", title="", **attrs):
                return {
                    "name": name,
                    "css_class": css_class,
                    "title": title,
                    **attrs,
                }

            def get_template_name(self, context):
                return f"dynamic_{context['name']}.svg"

        self.assertHTMLEqual(
            SvgComponent.render(kwargs={"name": "svg1"}),
            """
            <svg>Dynamic1</svg>
            """,
        )
        self.assertHTMLEqual(
            SvgComponent.render(kwargs={"name": "svg2"}),
            """
            <svg>Dynamic2</svg>
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_allows_to_override_get_template(self):
        class TestComponent(Component):
            def get_context_data(self, variable, **attrs):
                return {
                    "variable": variable,
                }

            def get_template(self, context):
                template_str = "Variable: <strong>{{ variable }}</strong>"
                return Template(template_str)

        rendered = TestComponent.render(kwargs={"variable": "test"})
        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong>
            """,
        )

    def test_typed(self):
        TestCompArgs = Tuple[int, str]

        class TestCompKwargs(TypedDict):
            variable: str
            another: int

        class TestCompData(TypedDict):
            abc: int

        class TestCompSlots(TypedDict):
            my_slot: str

        class TestComponent(Component[TestCompArgs, TestCompKwargs, TestCompData, TestCompSlots]):
            def get_context_data(self, var1, var2, variable, another, **attrs):
                return {
                    "variable": variable,
                }

            def get_template(self, context):
                template_str: types.django_html = """
                    {% load component_tags %}
                    Variable: <strong>{{ variable }}</strong>
                    {% slot 'my_slot' / %}
                """
                return Template(template_str)

        rendered = TestComponent.render(
            kwargs={"variable": "test", "another": 1},
            args=(123, "str"),
            slots={"my_slot": "MY_SLOT"},
        )

        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong> MY_SLOT
            """,
        )

    def test_input(self):
        tester = self

        class TestComponent(Component):
            @no_type_check
            def get_context_data(self, var1, var2, variable, another, **attrs):
                tester.assertEqual(self.input.args, (123, "str"))
                tester.assertEqual(self.input.kwargs, {"variable": "test", "another": 1})
                tester.assertIsInstance(self.input.context, Context)
                tester.assertEqual(self.input.slots, {"my_slot": "MY_SLOT"})

                return {
                    "variable": variable,
                }

            @no_type_check
            def get_template(self, context):
                tester.assertEqual(self.input.args, (123, "str"))
                tester.assertEqual(self.input.kwargs, {"variable": "test", "another": 1})
                tester.assertIsInstance(self.input.context, Context)
                tester.assertEqual(self.input.slots, {"my_slot": "MY_SLOT"})

                template_str: types.django_html = """
                    {% load component_tags %}
                    Variable: <strong>{{ variable }}</strong>
                    {% slot 'my_slot' / %}
                """
                return Template(template_str)

        rendered = TestComponent.render(
            kwargs={"variable": "test", "another": 1},
            args=(123, "str"),
            slots={"my_slot": "MY_SLOT"},
        )

        self.assertHTMLEqual(
            rendered,
            """
            Variable: <strong>test</strong> MY_SLOT
            """,
        )


class ComponentRenderTest(BaseTestCase):
    @parametrize_context_behavior(["django", "isolated"])
    def test_render_minimal(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, the_arg2=None, *args, the_kwarg=None, **kwargs):
                return {
                    "the_arg2": the_arg2,
                    "the_kwarg": the_kwarg,
                    "args": args,
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render()
        self.assertHTMLEqual(
            rendered,
            """
            the_arg2: None
            args: ()
            the_kwarg: None
            kwargs: {}
            ---
            from_context:
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_full(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                the_arg: {{ the_arg }}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_first: {% slot "first" required %}
                {% endslot %}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, the_arg, the_arg2=None, *args, the_kwarg, **kwargs):
                return {
                    "the_arg": the_arg,
                    "the_arg2": the_arg2,
                    "the_kwarg": the_kwarg,
                    "args": args,
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render(
            context={"from_context": 98},
            args=["one", "two", "three"],
            kwargs={"the_kwarg": "test", "kw2": "ooo"},
            slots={"first": "FIRST_SLOT"},
        )
        self.assertHTMLEqual(
            rendered,
            """
            the_arg: one
            the_arg2: two
            args: ('three',)
            the_kwarg: test
            kwargs: {'kw2': 'ooo'}
            ---
            from_context: 98
            ---
            slot_first: FIRST_SLOT
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_to_response_full(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                the_arg: {{ the_arg }}
                the_arg2: {{ the_arg2 }}
                args: {{ args|safe }}
                the_kwarg: {{ the_kwarg }}
                kwargs: {{ kwargs|safe }}
                ---
                from_context: {{ from_context }}
                ---
                slot_first: {% slot "first" required %}
                {% endslot %}
                ---
                slot_second: {% slot "second" default %}
                    SLOT_SECOND_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, the_arg, the_arg2=None, *args, the_kwarg, **kwargs):
                return {
                    "the_arg": the_arg,
                    "the_arg2": the_arg2,
                    "the_kwarg": the_kwarg,
                    "args": args,
                    "kwargs": kwargs,
                }

        rendered = SimpleComponent.render_to_response(
            context={"from_context": 98},
            args=["one", "two", "three"],
            kwargs={"the_kwarg": "test", "kw2": "ooo"},
            slots={"first": "FIRST_SLOT"},
        )
        self.assertIsInstance(rendered, HttpResponse)

        self.assertHTMLEqual(
            rendered.content.decode(),
            """
            the_arg: one
            the_arg2: two
            args: ('three',)
            the_kwarg: test
            kwargs: {'kw2': 'ooo'}
            ---
            from_context: 98
            ---
            slot_first: FIRST_SLOT
            ---
            slot_second: SLOT_SECOND_DEFAULT
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_to_response_change_response_class(self):
        class MyResponse:
            def __init__(self, content: str) -> None:
                self.content = bytes(content, "utf-8")

        class SimpleComponent(Component):
            response_class = MyResponse
            template: types.django_html = "HELLO"

        rendered = SimpleComponent.render_to_response()
        self.assertIsInstance(rendered, MyResponse)

        self.assertHTMLEqual(
            rendered.content.decode(),
            "HELLO",
        )

    @parametrize_context_behavior([("django", False), ("isolated", True)])
    def test_render_slot_as_func(self, context_behavior_data):
        is_isolated = context_behavior_data

        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                {% slot "first" required data1="abc" data2:hello="world" data2:one=123 %}
                    SLOT_DEFAULT
                {% endslot %}
            """

            def get_context_data(self, the_arg, the_kwarg=None, **kwargs):
                return {
                    "the_arg": the_arg,
                    "the_kwarg": the_kwarg,
                    "kwargs": kwargs,
                }

        def first_slot(ctx: Context, slot_data: Dict, slot_ref: SlotRef):
            self.assertIsInstance(ctx, Context)
            # NOTE: Since the slot has access to the Context object, it should behave
            # the same way as it does in templates - when in "isolated" mode, then the
            # slot fill has access only to the "root" context, but not to the data of
            # get_context_data() of SimpleComponent.
            if is_isolated:
                self.assertEqual(ctx.get("the_arg"), None)
                self.assertEqual(ctx.get("the_kwarg"), None)
                self.assertEqual(ctx.get("kwargs"), None)
                self.assertEqual(ctx.get("abc"), None)
            else:
                self.assertEqual(ctx["the_arg"], "1")
                self.assertEqual(ctx["the_kwarg"], 3)
                self.assertEqual(ctx["kwargs"], {})
                self.assertEqual(ctx["abc"], "def")

            slot_data_expected = {
                "data1": "abc",
                "data2": {"hello": "world", "one": 123},
            }
            self.assertDictEqual(slot_data_expected, slot_data)

            self.assertIsInstance(slot_ref, SlotRef)
            self.assertEqual("SLOT_DEFAULT", str(slot_ref).strip())

            return f"FROM_INSIDE_FIRST_SLOT | {slot_ref}"

        rendered = SimpleComponent.render(
            context={"abc": "def"},
            args=["1"],
            kwargs={"the_kwarg": 3},
            slots={"first": first_slot},
        )
        self.assertHTMLEqual(
            rendered,
            "FROM_INSIDE_FIRST_SLOT | SLOT_DEFAULT",
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_raises_on_missing_slot(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                {% slot "first" required %}
                {% endslot %}
            """

        with self.assertRaises(TemplateSyntaxError):
            SimpleComponent.render()

        SimpleComponent.render(
            slots={"first": "FIRST_SLOT"},
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_with_include(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render()
        self.assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    # See https://github.com/EmilStenstrom/django-components/issues/580
    # And https://github.com/EmilStenstrom/django-components/commit/fee26ec1d8b46b5ee065ca1ce6143889b0f96764
    @parametrize_context_behavior(["django", "isolated"])
    def test_render_with_include_and_context(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render(context=Context())
        self.assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    # See https://github.com/EmilStenstrom/django-components/issues/580
    # And https://github.com/EmilStenstrom/django-components/commit/fee26ec1d8b46b5ee065ca1ce6143889b0f96764
    @parametrize_context_behavior(["django", "isolated"])
    def test_render_with_include_and_request_context(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% load component_tags %}
                {% include 'slotted_template.html' %}
            """

        rendered = SimpleComponent.render(context=RequestContext(HttpRequest()))
        self.assertHTMLEqual(
            rendered,
            """
            <custom-template>
                <header>Default header</header>
                <main>Default main</main>
                <footer>Default footer</footer>
            </custom-template>
            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_with_extends(self):
        class SimpleComponent(Component):
            template: types.django_html = """
                {% extends 'block.html' %}
                {% block body %}
                    OVERRIDEN
                {% endblock %}
            """

        rendered = SimpleComponent.render()
        self.assertHTMLEqual(
            rendered,
            """
            <!DOCTYPE html>
            <html lang="en">
            <body>
                <main role="main">
                <div class='container main-container'>
                    OVERRIDEN
                </div>
                </main>
            </body>
            </html>

            """,
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_can_access_instance(self):
        class TestComponent(Component):
            template = "Variable: <strong>{{ id }}</strong>"

            def get_context_data(self, **attrs):
                return {
                    "id": self.component_id,
                }

        rendered = TestComponent(component_id="123").render()
        self.assertHTMLEqual(
            rendered,
            "Variable: <strong>123</strong>",
        )

    @parametrize_context_behavior(["django", "isolated"])
    def test_render_to_response_can_access_instance(self):
        class TestComponent(Component):
            template = "Variable: <strong>{{ id }}</strong>"

            def get_context_data(self, **attrs):
                return {
                    "id": self.component_id,
                }

        rendered_resp = TestComponent(component_id="123").render_to_response()
        self.assertHTMLEqual(
            rendered_resp.content.decode("utf-8"),
            "Variable: <strong>123</strong>",
        )

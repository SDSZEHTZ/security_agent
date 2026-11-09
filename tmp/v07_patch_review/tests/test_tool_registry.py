import unittest
from types import SimpleNamespace

from pydantic import BaseModel, Field

from runtime.tool_registry import ToolRegistry


class DemoArgs(BaseModel):

    query: str = Field(min_length=1)


class DemoTool:

    name = "search_code"

    args_model = DemoArgs

    def execute(self, args, context):

        return {
            "query": args.query
        }


class ToolRegistryTests(unittest.TestCase):

    def setUp(self):

        self.registry = ToolRegistry()

        self.tool = DemoTool()


    def test_registration_and_lookup(self):

        self.registry.register(self.tool)

        result = self.registry.get("search_code")

        self.assertIs(result, self.tool)


    def test_unknown_tool_returns_none(self):

        result = self.registry.get("unknown_tool")

        self.assertIsNone(result)


    def test_duplicate_tool_is_rejected(self):

        self.registry.register(self.tool)

        with self.assertRaisesRegex(
            ValueError,
            "DUPLICATE_TOOL"
        ):

            self.registry.register(DemoTool())

        self.assertIs(self.registry.get("search_code"), self.tool)


    def test_invalid_tool_is_rejected(self):

        with self.assertRaisesRegex(
            ValueError,
            "INVALID_TOOL_NAME"
        ):

            self.registry.register(object())


    def test_names_returns_registered_names(self):

        self.registry.register(self.tool)

        self.assertEqual(
            self.registry.names(),
            ("search_code",)
        )


    def test_invalid_names_are_rejected_without_registration(self):
        for name in (None, "", 123, "search-code", "search code"):
            with self.subTest(name=name):
                tool = SimpleNamespace(name=name, args_model=DemoArgs, execute=lambda args, context: {})
                with self.assertRaisesRegex(ValueError, "^INVALID_TOOL_NAME$"):
                    self.registry.register(tool)
                self.assertEqual(self.registry.names(), ())

    def test_invalid_args_models_are_rejected_without_registration(self):
        for args_model in (None, object, DemoArgs(query="eval(")):
            with self.subTest(args_model=args_model):
                tool = SimpleNamespace(name="search_code", args_model=args_model, execute=lambda args, context: {})
                with self.assertRaisesRegex(ValueError, "^INVALID_TOOL_ARGS_MODEL$"):
                    self.registry.register(tool)
                self.assertIsNone(self.registry.get("search_code"))

    def test_missing_or_noncallable_execute_is_rejected(self):
        for tool in (
            SimpleNamespace(name="search_code", args_model=DemoArgs),
            SimpleNamespace(name="search_code", args_model=DemoArgs, execute="not callable"),
        ):
            with self.subTest(tool=tool):
                with self.assertRaisesRegex(ValueError, "^INVALID_TOOL_IMPLEMENTATION$"):
                    self.registry.register(tool)
                self.assertEqual(self.registry.names(), ())

    def test_names_is_an_independent_snapshot(self):
        self.registry.register(self.tool)
        names = self.registry.names()
        another = DemoTool()
        another.name = "read_source"
        self.registry.register(another)
        self.assertIsInstance(names, tuple)
        self.assertEqual(names, ("search_code",))
        self.assertEqual(self.registry.names(), ("search_code", "read_source"))


if __name__ == "__main__":

    unittest.main()

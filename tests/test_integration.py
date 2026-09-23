"""Integration tests that exercise the UNO document layer against a running,
headless LibreOffice.

They are skipped unless ``HAILPER_TEST_PORT`` points at a UNO socket, so the
normal unit-test run (and the build job) are unaffected.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "copilot"))

PORT = os.environ.get("HAILPER_TEST_PORT")


class TestLibreOfficeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PORT:
            raise unittest.SkipTest("HAILPER_TEST_PORT not set")
        try:
            import uno
            from com.sun.star.connection import NoConnectException
        except Exception as error:  # noqa: BLE001
            raise unittest.SkipTest("python uno unavailable: %s" % error)
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local)
        url = ("uno:socket,host=127.0.0.1,port=%s;urp;"
               "StarOffice.ComponentContext" % PORT)
        try:
            cls.ctx = resolver.resolve(url)
        except NoConnectException as error:
            raise unittest.SkipTest("no LibreOffice listener: %s" % error)
        cls.desktop = cls.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", cls.ctx)

    def _writer(self):
        document = self.desktop.loadComponentFromURL(
            "private:factory/swriter", "_blank", 0, ())
        time.sleep(1)
        return document

    def test_insert_markdown(self):
        import cp_document
        document = self._writer()
        try:
            text = document.getText()
            cursor = text.createTextCursor()
            text.insertString(cursor, "Base", False)
            doc_ctx = cp_document.DocumentContext(self.ctx, document)
            self.assertTrue(doc_ctx.insert_markdown(
                "# Title\n\n**Sub**\n\n- one\n- two", "insert"))
            content = text.getString()
            self.assertIn("Title", content)
            self.assertIn("one", content)
        finally:
            document.close(False)

    def test_document_tools(self):
        import cp_document
        import cp_tools
        document = self._writer()
        try:
            text = document.getText()
            cursor = text.createTextCursor()
            text.insertString(cursor, "Hello", False)
            doc_ctx = cp_document.DocumentContext(self.ctx, document)
            read = cp_tools.execute(doc_ctx, "read_document", {}, {})
            self.assertIn("Hello", read)
            inserted = cp_tools.execute(
                doc_ctx, "insert_text", {"text": " world", "where": "end"}, {})
            self.assertIn("Inserted", inserted)
            self.assertIn("world", text.getString())
        finally:
            document.close(False)

    def test_replace_text(self):
        import cp_document
        import cp_tools
        document = self._writer()
        try:
            text = document.getText()
            cursor = text.createTextCursor()
            text.insertString(cursor, "The cat sat.", False)
            doc_ctx = cp_document.DocumentContext(self.ctx, document)
            result = cp_tools.execute(
                doc_ctx, "replace_text", {"find": "cat", "text": "dog"}, {})
            self.assertIn("Replaced", result)
            self.assertIn("dog", text.getString())
        finally:
            document.close(False)


if __name__ == "__main__":
    unittest.main()

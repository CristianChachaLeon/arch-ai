"""Tests for the patch file parser."""

from archai.cli.app import _parse_patch_file


class TestParsePatchFile:
    def test_parse_single_file_patch(self):
        patch = """--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
+import os
 def hello():
-    print("hi")
+    print("hello")
"""
        changes = _parse_patch_file(patch)
        assert len(changes) == 1
        assert changes[0].file_path == "src/main.py"
        assert "import os" in changes[0].patch

    def test_parse_multi_file_patch(self):
        patch = """--- a/src/a.py
+++ b/src/a.py
@@ -1 +1 @@
-x
+y
--- a/src/b.py
+++ b/src/b.py
@@ -1 +1 @@
-old
+new
"""
        changes = _parse_patch_file(patch)
        assert len(changes) == 2
        assert changes[0].file_path == "src/a.py"
        assert changes[1].file_path == "src/b.py"

    def test_parse_empty_patch(self):
        changes = _parse_patch_file("")
        assert changes == []

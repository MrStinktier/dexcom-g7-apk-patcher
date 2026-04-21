"""Tests for tools.lib — shared APK patching utilities."""
from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import pytest


class TestApktoolAvailable:
    def test_apktool_jar_exists(self):
        jar = Path("bin/apktool_2.7.0.jar")
        assert jar.exists(), f"apktool not found at {jar}"

    def test_apktool_runs(self):
        """apktool CLI must be callable."""
        result = subprocess.run(
            ["java", "-jar", "bin/apktool_2.7.0.jar", "--version"],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, f"apktool failed: {result.stderr}"


class TestLibImports:
    def test_lib_is_importable(self):
        import tools.lib as lib
        assert hasattr(lib, "detect_apk_version")
        assert hasattr(lib, "decompile_apk")
        assert hasattr(lib, "recompile_apk")
        assert hasattr(lib, "sign_apk")
        assert hasattr(lib, "extract_manifest")
        assert hasattr(lib, "parse_manifest")

    def test_version_detection_from_fake_zip(self, tmp_path):
        """Can read versionCode from an APK (zip) without decompiling."""
        import tools.lib as lib

        fake_apk = tmp_path / "fake.apk"
        manifest_xml = b"""<?xml version="1.0"?>
        <manifest package="com.dexcom.g7" versionCode="13519" versionName="2.11.2">
        </manifest>
        """
        with zipfile.ZipFile(fake_apk, "w") as z:
            z.writestr("AndroidManifest.xml", manifest_xml)

        info = lib.detect_apk_version(str(fake_apk))
        assert info["version_code"] == 13519
        assert info["version_name"] == "2.11.2"

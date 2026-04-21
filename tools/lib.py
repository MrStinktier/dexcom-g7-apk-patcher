"""Shared utilities for APK patching tools."""
from __future__ import annotations

import json
import os
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any

APKTOOL_JAR = Path("bin/apktool_2.7.0.jar")
UBER_SIGNER_JAR = Path("bin/uber-apk-signer-1.3.0.jar")
KEYSTORE = Path("signing.keystore")
KEYSTORE_PASS = "6dYlrOon6U1430fwj492dBjnYm8CN5zYcWdbVJ53GQIf7PExEV"


def detect_apk_version(apk_path: str | Path) -> dict[str, Any]:
    """Read versionCode/versionName from an APK without full decompilation.

    APK files are ZIPs. The AndroidManifest.xml inside contains the version info.
    We extract just the manifest entry to avoid a full decompile.
    """
    apk_path = Path(apk_path)
    with zipfile.ZipFile(apk_path, "r") as z:
        manifest_name = None
        for name in z.namelist():
            if name.endswith("AndroidManifest.xml"):
                manifest_name = name
                break

        if not manifest_name:
            return {"error": "No AndroidManifest.xml found in APK", "path": str(apk_path)}

        raw = z.read(manifest_name).decode("utf-8", errors="replace")

    # Android binary XML is compiled — try AAPT first as a reliable fallback
    version_info = _detect_via_aapt(apk_path)
    if version_info:
        return version_info

    # Fallback: regex on the raw bytes (works for some APKs)
    version_code = re.search(r'versionCode="(\d+)"', raw)
    version_name = re.search(r'versionName="([^"]+)"', raw)
    return {
        "path": str(apk_path),
        "version_code": int(version_code.group(1)) if version_code else None,
        "version_name": version_name.group(1) if version_name else None,
    }


def _detect_via_aapt(apk_path: Path) -> dict[str, Any] | None:
    """Use aapt/aapt2 to dump package info from the APK."""
    for aapt in ["aapt", "aapt2"]:
        try:
            result = subprocess.run(
                [aapt, "dump", "badging", str(apk_path)],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            version_code = re.search(r"package: versionCode='?(\d+)'?", output)
            version_name = re.search(r"package: versionName='([^']+)'?", output)
            sdk_version = re.search(r"sdkVersion:'?(\d+)'?", output)
            target_sdk = re.search(r"targetSdkVersion:'?(\d+)'?", output)
            if version_code:
                return {
                    "path": str(apk_path),
                    "version_code": int(version_code.group(1)),
                    "version_name": version_name.group(1) if version_name else None,
                    "sdk_version": int(sdk_version.group(1)) if sdk_version else None,
                    "target_sdk": int(target_sdk.group(1)) if target_sdk else None,
                }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def decompile_apk(apk_path: str, output_dir: str) -> subprocess.CompletedProcess:
    """Run apktool to decompile an APK into smali + resources."""
    cmd = ["java", "-jar", str(APKTOOL_JAR), "d", str(apk_path), "-o", str(output_dir), "-f"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def recompile_apk(source_dir: str, output_apk: str) -> subprocess.CompletedProcess:
    """Rebuild a decompiled directory into an APK."""
    cmd = ["java", "-jar", str(APKTOOL_JAR), "b", str(source_dir), "-o", str(output_apk), "--use-aapt2"]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


def sign_apk(unsigned_apk: str, output_apk: str | None = None) -> subprocess.CompletedProcess:
    """Sign an APK with the project's keystore."""
    output_apk = output_apk or unsigned_apk
    cmd = [
        "java", "-jar", str(UBER_SIGNER_JAR),
        "-a", str(unsigned_apk),
        "--ks", str(KEYSTORE),
        "--ksAlias", "cert",
        "--ksPass", KEYSTORE_PASS,
        "--ksKeyPass", KEYSTORE_PASS,
        "--overwrite",
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def extract_manifest(apk_path: str | Path, output_xml: str | Path) -> None:
    """Extract AndroidManifest.xml from APK without full decompilation."""
    apk_path = Path(apk_path)
    output_xml = Path(output_xml)
    output_xml.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(apk_path, "r") as z:
        for name in z.namelist():
            if name.endswith("AndroidManifest.xml"):
                z.extract(name, output_xml.parent)
                # Rename the extracted file to our target path
                extracted = output_xml.parent / name
                if extracted != output_xml:
                    extracted.rename(output_xml)
                break


def parse_manifest(xml_path: str | Path) -> dict[str, Any]:
    """Parse AndroidManifest.xml into a structured dict."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Android namespace variations
    ns_variants = [
        "http://schemas.android.com/apk/res/android",
        "urn:oas:names:tc:xliff:document:1.0",
    ]
    android_ns = ns_variants[0]

    services = []
    receivers = []
    activities = []
    applications = []

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        attrs = elem.attrib
        android_attrs = {k.split("}")[-1]: v for k, v in attrs.items() if "}" in k}
        plain_attrs = {k: v for k, v in attrs.items() if "}" not in k}

        if tag == "service":
            services.append({**plain_attrs, **android_attrs})
        elif tag == "receiver":
            receivers.append({**plain_attrs, **android_attrs})
        elif tag == "activity":
            activities.append({**plain_attrs, **android_attrs})
        elif tag == "application":
            applications.append({**plain_attrs, **android_attrs})

    return {
        "package": root.get("package", root.attrib.get("package")),
        "version_code": root.attrib.get("versionCode"),
        "version_name": root.attrib.get("versionName"),
        "services": services,
        "receivers": receivers,
        "activities": activities,
        "applications": applications,
    }


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Load a saved APK manifest from JSON."""
    with open(manifest_path) as f:
        return json.load(f)


def save_manifest(manifest: dict[str, Any], manifest_path: str | Path) -> None:
    """Save APK manifest to JSON."""
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def find_smali_class(base_dir: str | Path, class_pattern: str) -> list[Path]:
    """Find all smali files matching a class name or path fragment."""
    base_dir = Path(base_dir)
    matches = []
    for smali_file in base_dir.rglob("*.smali"):
        if class_pattern in smali_file.as_posix():
            matches.append(smali_file)
    return matches

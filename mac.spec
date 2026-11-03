# -*- mode: python ; coding: utf-8 -*-
# macOS build spec for Sprite Sage.
# Differs from main.spec (Windows-only):
#   - no PyInstaller.utils.win32.versioninfo import
#   - produces a .app BUNDLE instead of a bare EXE
#   - derives an .icns from graphics/wizard.gif when Pillow is available

import sys
import runpy
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_all,
)

ROOT = Path.cwd()
SRC_DIR = ROOT / "src"
APP_VERSION = runpy.run_path(str(SRC_DIR / "spritesage" / "__init__.py"))["__version__"]


def _is_google_genai_runtime_module(name):
    return ".tests" not in name and not name.endswith("._test_api_client")


# Release builds must run from a virtual environment.
if sys.prefix == sys.base_prefix:
    raise RuntimeError(
        "Release builds must run from the project virtual environment. "
        "Use ./venv/bin/python -m PyInstaller mac.spec"
    )

import torch

if torch.version.cuda is not None:
    raise RuntimeError(
        f"Refusing to bundle CUDA-enabled Torch {torch.__version__}. "
        "Install the pinned CPU-only release dependencies."
    )
if torch.__version__.split("+", 1)[0] != "1.13.1":
    raise RuntimeError(
        f"Expected Torch 1.13.1 for the release build, found {torch.__version__}."
    )

google_genai_submodules = collect_submodules(
    "google.genai", filter=_is_google_genai_runtime_module
)
google_genai_data = collect_data_files("google.genai", excludes=["tests/**"])

safetensors_datas, safetensors_binaries, safetensors_hiddenimports = collect_all(
    "safetensors"
)
model_baker_submodules = collect_submodules("spritesage.model_baker")
model_manager_submodules = collect_submodules("modelmanager")
model_manager_data = collect_data_files("modelmanager")
pygltflib_submodules = collect_submodules("pygltflib")

# Build an .icns from the wizard GIF so the app has a branded icon on macOS.
icon_arg = None
try:
    from PIL import Image
    import subprocess
    import tempfile

    gif = Image.open(str(ROOT / "graphics" / "wizard.gif"))
    frame = gif.convert("RGBA")
    iconset = Path(tempfile.mkdtemp()) / "spritesage.iconset"
    iconset.mkdir()
    for size in (16, 32, 64, 128, 256, 512):
        frame.resize((size, size)).save(str(iconset / f"icon_{size}x{size}.png"))
        frame.resize((size, size)).save(str(iconset / f"icon_{size}x{size}@2x.png"))
    icns = ROOT / "build" / "spritesage.icns"
    icns.parent.mkdir(exist_ok=True)
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True
    )
    icon_arg = str(icns)
except Exception as exc:  # icon is cosmetic; never block the build on it
    print(f"[mac.spec] Icon conversion skipped: {exc}")

a = Analysis(
    ["src/spritesage/main.py"],
    pathex=[str(SRC_DIR)],
    binaries=safetensors_binaries,
    datas=[
        ("graphics", "graphics"),
        (
            "src/spritesage/assets/motion_templates/bandit.glb",
            "spritesage/assets/motion_templates",
        ),
    ]
    + safetensors_datas
    + google_genai_data
    + model_manager_data,
    hiddenimports=(
        google_genai_submodules
        + safetensors_hiddenimports
        + model_baker_submodules
        + model_manager_submodules
        + pygltflib_submodules
        + ["numpy.core._multiarray_umath"]
    ),
    excludes=[
        "IPython",
        "astropy",
        "diffusers",
        "gradio",
        "jupyter",
        "matplotlib",
        "numba",
        "pandas",
        "pyarrow",
        "pytest",
        "scipy",
        "transformers",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="spritesage",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name="SpriteSage.app",
    icon=icon_arg,
    bundle_identifier="com.keystoneintelligence.spritesage",
    info_plist={
        "CFBundleName": "Sprite Sage",
        "CFBundleDisplayName": "Sprite Sage",
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "NSHighResolutionCapable": True,
    },
)

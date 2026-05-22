from __future__ import annotations

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent
VERSION = "0.1.0"


def get_requirements() -> list[str]:
    requirements = ROOT / "requirements.txt"
    return [
        line.strip()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


setup(
    name="writevewhere",
    version=VERSION,
    author="Azusagwa",
    license="GPLv3",
    description="A lightweight PySide6 screen annotation app.",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    install_requires=get_requirements(),
    python_requires=">=3.10",
    entry_points={
        "gui_scripts": [
            "writevewhere=writevewhere.app:main",
        ],
    },
    packages=find_packages("."),
    package_data={
        "writevewhere": ["assets/ui/*.png"],
    },
    url="https://github.com/Azusagwa/writevewhere",
    classifiers=[
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Multimedia :: Graphics :: Capture :: Screen Capture",
    ],
)

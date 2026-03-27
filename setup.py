from setuptools import setup, find_packages

setup(
    name="finorg",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "finorg=finorg.cli:main",
        ],
    },
    install_requires=[
        "pymupdf",
        "Pillow",
        "tqdm",
        "rich",
        "requests",
        "pydantic",
        "orjson",
        "click",
        "pathvalidate",
        "xxhash",
    ],
)

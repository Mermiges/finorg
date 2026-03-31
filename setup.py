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
    extras_require={
        "lightonocr": [
            "transformers>=5.0.0",
            "accelerate>=1.10.0",
            "huggingface_hub>=1.0.0",
        ],
        "docling": [
            "docling",
        ],
        "marker": [
            "marker-pdf",
        ],
        "dev": [
            "pytest",
        ],
    },
)

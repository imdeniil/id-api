from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="id-api",
    version="0.1.0",
    author="Павлючик Даниил",
    author_email="keemor821@gmail.com",
    description="Гибкая HTTP-клиентская библиотека с поддержкой JWT и OAuth2 аутентификации",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/imdeniil/id-api",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: AsyncIO",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests>=2.25.0",
        "aiohttp>=3.7.0",
    ],
    keywords="http client api jwt oauth2 async aiohttp requests",
)
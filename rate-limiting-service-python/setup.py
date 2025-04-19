"""
Setup script for rate-limiter-service package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="rate-limiter-service",
    version="1.0.0",
    author="",
    author_email="",
    description="Robust rate limiting service for API stability and performance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/rate-limiting-service-python",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=[
        "aioredis>=2.0.0",
        "fastapi>=0.68.0",
        "flask>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-asyncio>=0.15.0",
            "pytest-cov>=2.12.0",
            "black>=21.5b2",
            "isort>=5.9.0",
        ],
        "docs": [
            "mkdocs>=1.2.0",
            "mkdocs-material>=7.1.0",
        ],
    },
) 
"""
This makes a package of the crawler. We mostly plan to use this package
in a editable mode, straight from git.

Still, things are a lot simpler for Poetry if we make a package out of it. Then Poetry
handles the Python import paths without us having to do dirty packs to get it to
import properly whilst maintaining a src-style directory structure.

"""

import setuptools

setuptools.setup(
    name="entraos-metasys-crawler-cli",
    version="0.1.9",
    author="Per Buer",
    author_email="per.buer@gmail.com",
    description="Metasys crawler",
    long_description="Metasys crawler",
    long_description_content_type="text/markdown",
    url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache-2.0",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)

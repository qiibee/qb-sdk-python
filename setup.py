import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="qb-sdk",
    version="0.0.1",
    author="Qiibee",
    author_email="tech@qiibee.com",
    description="A small example package",
    long_description="SDK for brands to access the qiibee loyalty blockchain.",
    long_description_content_type="text/markdown",
    url="https://github.com/qiibee/qb-sdk-python",
    packages=setuptools.find_packages(),
    install_requires=['requests>=1.0.0'],
    classifiers=[
        "Programming Language :: Python :: 3",
        'Programming Language :: Python :: 3.5',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords=['qiibee', 'api', 'sdk', 'blockchain', 'loyalty']
)
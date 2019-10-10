import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

requirements_file = 'requirements.txt'

setuptools.setup(
    name="qb-sdk",
    version="0.0.1",
    author="qiibee",
    author_email="tech@qiibee.com",
    description="qiibee loyalty blockchain brand SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/qiibee/qb-sdk-python",
    packages=setuptools.find_packages(),
    python_requires='>=3.5',
    install_requires=[
        'requests>=1.0.0',
        'web3>=5.0.0',
        'eth-utils>=1.6.0,<2.0.0',
        'eth-keys<0.3.0,>=0.2.1',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        'Programming Language :: Python :: 3.5',
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords=['qiibee', 'api', 'sdk', 'blockchain', 'loyalty', 'QBX']
)

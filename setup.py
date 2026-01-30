from setuptools import setup, find_packages

setup(
    name="outrider",
    version="0.1.0",
    description="Automate OCI image transfer to air-gapped and remote systems",
    author="",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.8",
    install_requires=[
        "paramiko>=3.4.0",
        "pyyaml>=6.0.1",
        "click>=8.1.7",
    ],
    entry_points={
        "console_scripts": [
            "outrider=outrider.cli:main",
        ],
    },
    include_package_data=True,
)

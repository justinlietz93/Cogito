from setuptools import setup, find_packages

setup(
    name="cogito",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'cogito-thesizer=src.syncretic_catalyst.thesis_builder:main',
        ],
    },
)
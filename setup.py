from setuptools import setup, packages
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='wynbot',
    version='0.1.0',
    description='Mimic your Hangouts contacts based on your chat history',
    long_description=long_description,
    url='https://github.com/ammgws/wynbot',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.6',
    ],
    python_requires='>=3.6',
    packages=find_packages(exclude=['tests']),
    install_requires=['click, markovify, nltk'],
    dependency_links=['https://github.com/ammgws/hangouts_client/tarball/master']
)

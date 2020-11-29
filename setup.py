import setuptools

setuptools.setup(
    name='derivatives',
    version='0.1.dev0',
    license='MIT Licence',
    author='ethframe',
    description='Lexer generator based on regular expressions derivatives',
    url='https://github.com/ethframe/derivatives',
    packages=setuptools.find_packages(exclude=['tests']),
    zip_safe=False,
)

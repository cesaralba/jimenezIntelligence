from setuptools import setup

setup(
        name="SMACB",
        version_format='0.1.dev{commitcount}+{gitsha}',
        setup_requires=['setuptools-git-version'],
        version="0.1",
        packages=['SMACB'],
)

setup(
        name="Utils",
        version_format='0.1.dev{commitcount}+{gitsha}',
        setup_requires=['setuptools-git-version'],
        version="0.1",
        packages=['Utils'],
)

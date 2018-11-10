from setuptools import find_packages, setup

setup(
    name="jimInt",
    version_format='0.1.dev{commitcount}+{gitsha}',
    setup_requires=['setuptools-git-version'],
    version="0.1",
    packages=find_packages(exclude=['tests/*']),
)

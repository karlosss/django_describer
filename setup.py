import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="django_describer",
    version="0.0.22",
    author="Karel Jilek",
    author_email="los.karlosss@gmail.com",
    description="A tool for automated generation of several APIs from a Django webapp.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/karlosss/django_describer",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "django",
        "django-filter",
        "graphene",
        "graphene-django",
        "graphene-django-extras",
    ],
    python_requires='>=3.6',
)

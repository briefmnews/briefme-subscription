from setuptools import setup

setup(
    name="briefme-subscription",
    version="0.0.1",
    description="Base subscription app for Brief.me projects",
    url="https://github.com/briefmnews/briefme-subscrition",
    author="Brief.me",
    author_email="tech@brief.me",
    license="None",
    packages=["briefme_subscription"],
    python_requires=">=3.7",
    install_requires=[
        "Django>=2.2",
        "django-model-utils>=3",
        "python-dateutil>=2.8"
    ],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 2.2",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    include_package_data=True,
    zip_safe=False,
)

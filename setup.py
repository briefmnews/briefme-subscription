from setuptools import setup

setup(
    name="briefme-subscription",
    version="3.1.0",
    description="Base subscription app for Brief.me projects",
    url="https://github.com/briefmnews/briefme-subscrition",
    author="Brief.me",
    author_email="tech@brief.me",
    license="None",
    packages=["briefme_subscription", "briefme_subscription.views"],
    python_requires=">=3.7",
    install_requires=[
        "analytics-python>=1.3.0,<2",
        "Django>=2.2,<3",
        "django-model-utils>=4,<5",
        "python-dateutil>=2.8,<3",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    include_package_data=True,
    zip_safe=False,
)

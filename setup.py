from distribute_setup import use_setuptools
use_setuptools()
import os
import autonomoustorrent
from setuptools import setup, find_packages


# Start with a clean slate to prevent side-effects
if os.path.exists('dist/'): shutil.rmtree('dist/')
if os.path.exists('build/'): shutil.rmtree('build/')


setup(
    name = "AutonomoTorrent",
    version = autonomoustorrent.__version__,
    #author = "Josh S. Ziegler",
    author_email = "josh.s.ziegler@gmail.com",
    description = "AutonomoTorrent %s" % autonomoustorrent.__version__,
    long_description = """A minima, pure-python BitTorrent client.
        """,
    license = "GPLv3",
    keywords = "bittorrent client",
    url = "http://github.com/joshsziegler/AutonomoTorrent",
    classifiers = [
        'Topic :: Internet',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
    ],
    # End Meta-Data
    packages = find_packages(),
    scripts = [],
    entry_points = {
        'console_scripts': [
            'autonomo = autonomoustorrent.__main__:console',
        ],
        'gui_scripts':[
        ]
    },
    install_requires = [
        'Twisted >= 10.0, < 10.3',
    ],
    package_data = {
        '': ['*.markdown'],
    },
    exclude_package_data = {
        '': [],
    },
    zip_safe = True,
)

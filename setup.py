from distribute_setup import use_setuptools
use_setuptools()
import os
import shutil
import autonomotorrent
from setuptools import setup, find_packages


# Start with a clean slate to prevent side-effects
if os.path.exists('dist/'): shutil.rmtree('dist/')
if os.path.exists('build/'): shutil.rmtree('build/')


setup(
    name = "AutonomoTorrent",
    version = autonomotorrent.__version__,
    author = "Josh S. Ziegler",
    author_email = "josh.s.ziegler@gmail.com",
    description = "AutonomoTorrent %s" % autonomotorrent.__version__,
    long_description = """A minimal, pure-python BitTorrent client.

        Supports:
            - DHT
            - Multi-trackers
            - Trackerless mode & Global peers pool
        """,
    license = "GPLv3",
    keywords = "bittorrent client",
    url = "http://github.com/joshsziegler/AutonomoTorrent",
    classifiers = [
        'Topic :: Internet',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
    ],
    # End Meta-Data
    packages = find_packages(),
    scripts = [],
    entry_points = {
        'console_scripts': [
            'autonomo = autonomotorrent.__main__:console',
        ],
        'gui_scripts':[
        ]
    },
    install_requires = [
        'Twisted >= 10.2',
    ],
    package_data = {
        '': ['*.markdown'],
    },
    exclude_package_data = {
        '': [],
    },
    zip_safe = True,
)

from setuptools import setup

APP = ['log_viewer.py']

OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'icon.icns',
    'packages': [
        'flask',
        'telnetlib3',
        'asyncio'
    ],
    'plist': {
        'CFBundleName': 'Log Viewer',
        'CFBundleDisplayName': 'Log Viewer',
        'CFBundleIdentifier': 'com.roku.logviewer',
        'CFBundleVersion': '1.0',
        'CFBundleShortVersionString': '1.0',
        'LSUIElement': False,
    }
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

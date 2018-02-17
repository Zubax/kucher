# Kucher

Kucher is a configuration, management, and diagnostic GUI tool for the
[Telega motor control platform](https://zubax.com/telega).

Kucher is an open source product distributed under the terms of the GPLv3 license.

Kucher is cross-platform. It is designed to run on Linux, Windows, and OSX alike.

Get support and ask questions at [forum.zubax.com](https://forum.zubax.com).

## Installation

## Usage

## Development

This section describes how to configure the local system for development.
An AMD64 GNU/Linux system is required.

### Getting the right version of Python

Kucher requires Python 3.6 or newer.
You can check whether you have the right version by running `python3 --version`.
If you already have Python 3.6 or newer as default, **skip this step**.
If a newer Python is needed, and you're running Ubuntu,
consider following this guide: <https://askubuntu.com/a/865569/91947>.

Once the new Python is installed, make sure that it works: `python3.6 --version`,
and then make it default:

```bash
sudo rm /usr/bin/python3
sudo ln -s /usr/bin/python3.6 /usr/bin/python3
```

Now run `python3 --version` and ensure that you have v3.6 as default.

### The rest of the owl

*setup.py is not yet written*

TODO: PyQt5>=5.9

TODO: pyserial>=3.6

TODO: numpy>=1.14

```bash
sudo pip3 install pyqt5 pyserial
git clone --recursive https://github.com/Zubax/kucher
```

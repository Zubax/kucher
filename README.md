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

Kucher requires Python version 3.6 or newer.
If your system uses an older version, please refer to the section below to install
Python 3.6 before continuing.

*setup.py is not yet written*

TODO: PyQt5>=5.9

TODO: pyserial>=3.6

TODO: numpy>=1.14

```bash
pip3 install PyQt5 pyserial  # You may need to run this as root depending on your environment
git clone --recursive https://github.com/Zubax/kucher
```

### Running the application

Regular launch from sources:

```bash
cd kucher
./main.py
```

The following command line options are available:


* `--debug` - activates verbose logging; useful for troubleshooting.
* `--test` - run unit tests.
    * `-k` - can be used in conjunction with `--test` to run a specific test.
    Refer to the PyTest documentation for more information.
    * Other options can be provided with `--test`; they will be passed directly to
    the PyTest framework.


### Getting the right version of Python

Kucher requires Python 3.6 or newer.
You can check whether you have the right version by running `python3 --version`.
If a newer Python is needed, and you're running Ubuntu, execute the following commands:

```bash
sudo apt-get install -y build-essential libbz2-dev libssl-dev libreadline-dev libsqlite3-dev tk-dev libpng-dev libfreetype6-dev
# Follow the instructions in the output of the above command!
curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
pyenv install 3.6.4
pyenv global 3.6.4
```

Now run `python3 --version` and ensure that you have v3.6 as default.

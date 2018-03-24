# Kucher

**Kucher is a configuration, management, and diagnostic GUI tool for the
[Telega motor control platform](https://zubax.com/technologies/telega).**

Kucher is an open source product distributed under the terms of the GPLv3 license.

Kucher is cross-platform. It is designed to run at least on GNU/Linux and Windows;
it is also compatible with some other platforms, such as OS X,
but is not actively tested against them.

## Installation

Simply download a version suitable for your OS from
**[files.zubax.com/products/com.zubax.kucher](https://files.zubax.com/products/com.zubax.kucher)**
and run it.
If you don't see a suitable version published there, please open a ticket.

## Usage

Please refer to the Telega home page at
**[zubax.com/technologies/telega](https://zubax.com/technologies/telega)**
for links to documentation and examples.

Get support and ask questions at **[forum.zubax.com](https://forum.zubax.com)**.

## Development

### Conventions

Follow PEP8 with one exception: the maximum line length shall be 120 characters.
Find more info on the [Zubax Knowledge Base article](https://kb.zubax.com/x/_oAh).

We are using PyCharm with PEP8 compliance checks enabled.
Non-conforming contributions should not be accepted.

### Configuring the environment

This section describes how to configure the local system for development.
An AMD64 GNU/Linux system is required.

Kucher requires Python version 3.6 or newer.
If your system uses an older version, please refer to the section below to install
Python 3.6 before continuing.

```bash
git clone --recursive https://github.com/Zubax/kucher
cd kucher
pip3 install -r requirements.txt  # You may need to run this as root depending on your environment
```

### Running the application

Just execute `zubax-kucher`.
The following command line options are available:

* `--debug` - activates verbose logging; useful for troubleshooting.
* `--profile` - creates a profile file after the application is closed.
* `--test` - run unit tests.
    * `-k` - can be used in conjunction with `--test` to run a specific test.
    Refer to the PyTest documentation for more information.
    * Other options can be provided with `--test`; they will be passed directly to
    the PyTest framework.

### Getting the right version of Python

Kucher requires Python 3.6 or newer.
You can check whether you have the right version by running `python3 --version`.
If a newer Python is needed, and you're running Ubuntu or an Ubuntu-based distro such as Mint,
execute the following commands:

```bash
sudo apt-get install -y git-core curl build-essential libsqlite3-dev
sudo apt-get install -y libbz2-dev libssl-dev libreadline-dev libsqlite3-dev tk-dev libpng-dev libfreetype6-dev
curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash
```

Follow the instructions in the output of the last command above.
**WARNING:** If the above command tells you to use `~/.bash_profile`,
disregard that and use `~/.bashrc` instead.

Reload the bash profile configuration
(e.g. close the current shell session and open a new one).
Then continue:

```
PYTHON_CONFIGURE_OPTS='--enable-shared' pyenv install 3.6.4
pyenv global 3.6.4
```

If there was a warning that `sqlite3` has not been compiled,
make sure to resolve it first before continuing - `sqlite3` is required by Kucher.
Now run `python3 --version` and ensure that you have v3.6 as default.

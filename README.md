[![Join the chat at https://gitter.im/Zubax/general](https://img.shields.io/badge/GITTER-join%20chat-green.svg)](https://gitter.im/Zubax/general)

# Kucher

**Kucher is a configuration, management, and diagnostic GUI tool for the
[Telega motor control platform](https://zubax.com/technologies/telega).**

Kucher is an open source product distributed under the terms of the GPLv3 license.

Kucher is cross-platform. It is designed to run at least on GNU/Linux and Windows;
it is also compatible with some other platforms, such as OS X,
but is not actively tested against them.

## Installation and usage

Kucher installation and setup instructions can be found at the
[Telega home page](https://zubax.com/technologies/telega).
If you don't see a version suitable for your OS published there, please open a ticket.
Links to usage instructions and examples can be found there as well.

Get support and ask questions at the [Zubax Forum](https://forum.zubax.com).

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

### Running the unit tests

From the root directory, on Linux:

```bash
pytest
```

On Windows:

```bash
pytest
```


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

### CI artifacts

The CI builds redistributable release binaries automatically.
Follow the CI status link from the [commits page](https://github.com/Zubax/kucher/commits/master)
to find the binaries for a particular commit.
The Linux binaries can be shipped directly; the Windows binaries must be signed first.

### Signing Windows executables

Requirements:
* Windows 10
* An unsigned executable file named `Kucher.exe`
* Certum cryptographic card (USB dongle), with a valid certificate installed
* Signtool: available in [Windows development Kit](https://developer.microsoft.com/en-us/windows/downloads/windows-10-sdk)

1 - Connect the USB dongle to the PC. Open it, launch "Start.exe", click "Install Code Signing" and follow the instructions. 
Reboot the system if required.

2 - Launch proCertum CardManager. Click "Options" and tick the box "EV Code Signing - replace CSP with minidriver library".
Click "Ok" and reboot the system.

3 - Make sure that signtool is included in the [Windows PATH variable](https://www.architectryan.com/2018/03/17/add-to-the-path-on-windows-10/).
Its path usually is
`C:\Program Files (x86)\Windows Kits\10\App Certification Kit`.

4 - Open command prompt and use this command the executable's directory:
```bash
signtool sign /n "Open Source Developer, Pavel Kirienko" /t http://time.certum.pl /fd sha256 /v Kucher.exe
```
Enter the card's PIN when asked. The executable should now be signed.

5 - To verify the file, use:
```bash
signtool verify /pa Kucher.exe
```

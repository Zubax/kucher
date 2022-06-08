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

Kucher requires Python version 3.10 or newer.

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

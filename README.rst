Formhub Server Setup
====================

Overview
--------

Does the intial installation and configuration of formhub server setup on a new ubuntu machine.

Installation
------------
$ pip install -r requirements.pip

Usage
-----

Configure local.configs.yaml and fabfile's default host string accordingly, then run the command:

$ fab server_setup:default deploy:default server_config:default


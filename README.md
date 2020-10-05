### Setup modified Acapy

1. Setup the initial enviroment first using the instructions from here https://github.com/THCLab/aries
2. Clone this repositiory into the aries folder from the first step
3. Add a volume to both agent instances pointing to the replacement aries_cloudagent like so:

```
volumes:
        - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
```


Full version:
```
  agent1.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
        - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
    ports:
      - '8150:8150'
    environment:
      AGENT_NAME: "Bob Smith"
      ACAPY_ENDPOINT: http://agent1.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server1:5000
    networks:
      - von_von

  agent2.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
        - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
    ports:
      - '8151:8150'
    environment:
      AGENT_NAME: "Alice Jones"
      ACAPY_ENDPOINT: http://agent2.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server2:5000
    networks:
      - von_von
```

### Setup service plugin volume

1. Clone this repo https://github.com/THCLab/aries-services-plugin into the aries folder from step 1
<!-- 2. You need to swap the startup.sh script inside the agents docker containers using the volumes which is located in /home/indy/ let's first prepera -->
2. You need to insert the services plugin into the docker container /home/indy/ using the docker volumes like so:

```
volumes:
        - ./aries-services-plugin/services/:/home/indy/services
```

Full version:
```
  agent1.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
            - ./aries-services-plugin/services/:/home/indy/services
    ports:
      - '8150:8150'
    environment:
      AGENT_NAME: "Bob Smith"
      ACAPY_ENDPOINT: http://agent1.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server1:5000
    networks:
      - von_von

  agent2.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
            - ./aries-services-plugin/services/:/home/indy/services
    ports:
      - '8151:8150'
    environment:
      AGENT_NAME: "Alice Jones"
      ACAPY_ENDPOINT: http://agent2.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server2:5000
    networks:
      - von_von
```
3. New endpoints should appear inside the acapy swagger admin API under http://localhost:8150


### Setup Vanilla Acapy compatible with external tests using jupyter notebook controller

1. Clone this repo (service plugin) https://github.com/THCLab/aries-services-plugin/tree/for-testing-vanilla-acapy into the aries folder from step 1
2. Clone (acapy 0.5.4) https://github.com/hyperledger/aries-cloudagent-python/tree/0.5.4 into the aries folder from step 1. Version 0.5.4. There is no guarantee that later or older versions wont break.
3. Mount both the cloned agent and the plugin into docker volumes, this will swap the files inside the container with the versions you cloned, like so:

```
volumes:
        - ./aries-services-plugin/services/:/home/indy/services
        - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
```

Full version:
```
  agent1.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
            - ./aries-services-plugin/services/:/home/indy/services
            - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
    ports:
      - '8150:8150'
    environment:
      AGENT_NAME: "Bob Smith"
      ACAPY_ENDPOINT: http://agent1.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server1:5000
    networks:
      - von_von

  agent2.localhost:
    image: humancolossus/agent:version-0.5.4-ext-1
    command: /bin/bash -c "./startup.sh"
    volumes:
            - ./aries-services-plugin/services/:/home/indy/services
            - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
    ports:
      - '8151:8150'
    environment:
      AGENT_NAME: "Alice Jones"
      ACAPY_ENDPOINT: http://agent2.localhost
      SWAGGER_INBOUND_PORT: 8150
      GENESIS_URL: http://webserver:8000/genesis
      WEBHOOK_URL: ws://websocket_server2:5000
    networks:
      - von_von
```
4. New endpoints should appear inside the acapy swagger admin API under http://localhost:8150
5. Tests are located in the aries-services-plugin/controllers



### Setup Debugger

To enable the debugger you need to pass in the --debug flag to the Acapy start command, this will make the agent wait for a debugger attach, preventing any startup actions.

To have good compatibility between the source code inside the container and what you have locally its probably a good idea to add a volume to the docker compose this way the code inside the container is always exactly what you have locally

```
volumes:
         - ./aries-cloudagent-python/aries_cloudagent/:/home/indy/aries_cloudagent
```

The debugger server by default starts on a 5678 port which needs to be published outside of the container like so in docker-compose:
```
ports:
          - 8152:5678
```

```
where:
	  - portToPublishTo:portInsideContainer
```

If the agent is waiting with the port published than we can attach to it using the ptvsd debugger and VSCode, you might need download the ptvsd using pip like so:

> pip3 install ptvsd

Finally to begin debugging openup the acapy source code that is also mounted using a volume inside a docker container and click Ctrl + Shift + P (The command menu) type in "open launch.json" and paste in this code into the launch.json file:

```
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "port": 8152,
            "host": "localhost",
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}/aries_cloudagent",
                    "remoteRoot": "/home/indy/aries_cloudagent"
                }
            ]
        }
    ]
}
```
Make sure that pathMappings match exactly to what you have on your setup
Make sure that you use the correct port

To start debugging hit Ctrl + Shift + P (The command menu) type in start debugging.

### Present Proof 

* Proof presentation step might not work properly if all the schema fields are not filled so that it doesnt have the None value(can be filled even with meaningless info)
* Errors seem to be propagated to the next stage of the protocol, even though first stage passed the next stage can throw a invalid structure error

### Code Keywords to look for what changed (case insensitive)

* Original
* Krzosa
* THCF












# Hyperledger Aries Cloud Agent - Python  <!-- omit in toc -->

[![pypi releases](https://img.shields.io/pypi/v/aries_cloudagent)](https://pypi.org/project/aries-cloudagent/)
[![CircleCI](https://circleci.com/gh/hyperledger/aries-cloudagent-python.svg?style=shield)](https://circleci.com/gh/hyperledger/aries-cloudagent-python)
[![codecov](https://codecov.io/gh/hyperledger/aries-cloudagent-python/branch/master/graph/badge.svg)](https://codecov.io/gh/hyperledger/aries-cloudagent-python)

<!-- ![logo](/docs/assets/aries-cloudagent-python-logo-bw.png) -->

> An easy to use Aries agent for building SSI services using any language that supports sending/receiving HTTP requests.

Hyperledger Aries Cloud Agent Python (ACA-Py) is a foundation for building self-sovereign identity (SSI) / decentralized identity services running in non-mobile environments using DIDcomm messaging, the did:peer DID method, and verifiable credentials. With ACA-Py, SSI developers can focus on building services using familiar web development technologies instead of trying to learn the nuts and bolts of low-level SDKs.

As we create ACA-Py, we're also building resources so that developers with a wide-range of backgrounds can get productive with ACA-Py in a hurry. Checkout the [resources](#resources) section below and jump in.

The "cloud" in Aries Cloud Agent - Python does **NOT** mean that ACA-Py cannot be used as an edge agent. ACA-Py is suitable for use in any non-mobile agent scenario, including as an enterprise edge agent for
issuing, verifying and holding verifiable credentials.

## Table of Contents <!-- omit in toc -->

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Security](#security)
- [API](#api)
- [Resources](#resources)
  - [Quickstart](#quickstart)
  - [Architectural Deep Dive](#architectural-deep-dive)
  - [Getting Started Guide](#getting-started-guide)
  - [Read the Docs](#read-the-docs)
  - [What to Focus On?](#what-to-focus-on)
- [Credit](#credit)
- [Contributing](#contributing)
- [License](#license)

## Background

Developing an ACA-Py-based application is pretty straight forward for those familiar with web development. An ACA-Py instance is always deployed with a paired "controller" application that provides the business logic for that ACA-Py agent. The controller receives webhook event notifications from its instance of ACA-Py and uses an HTTP API exposed by the ACA-Py instance to provide direction on how to respond to those events. No ACA-Py/Python development is needed--just deploy an ACA-Py instance from PyPi (examples available). The source of the business logic is your imagination. An interface to a legacy system? A user interface for a person? Custom code to implement a new service? You can build your controller in any language that supports making and receiving HTTP requests. Wait...that's every language!

ACA-Py currently supports "only" Hyperledger Indy's verifiable credentials scheme (which is pretty powerful). We are experimenting with adding support to ACA-Py for other DID Ledgers and verifiable credential schemes.

ACA-Py is built on the Aries concepts and features defined in the [Aries RFC](https://github.com/hyperledger/aries-rfcs) repository. [This document](https://github.com/hyperledger/aries-cloudagent-python/blob/master/SupportedRFCs.md) contains a (reasonably up to date) list of supported Aries RFCs by the current ACA-Py implementation.

## Install

ACA-Py can be run with docker without installation, or can be installed [from PyPi](https://pypi.org/project/aries-cloudagent/). Use the following command to install it locally:

```bash
pip install aries-cloudagent
```

## Usage

Instructions for running ACA-Py can be [found here](https://github.com/hyperledger/aries-cloudagent-python/blob/master/DevReadMe.md#running).

## Security

The administrative API exposed by the agent for the controller to use must be protected with an API key
(using the `--admin-api-key` command line arg) or deliberately left unsecured using the
`--admin-insecure-mode` command line arg. The latter should not be used other than in development if the API
is not otherwise secured.

## API

A deployed instance of an ACA-Py agent assembles an OpenAPI-documented REST interface from the protocols loaded with the agent. This is used by a controller application (written in any language) to manage the behaviour of the agent. The controller can initiate agent actions such as issuing a credential, and can respond to agent events, such
as sending a presentation request after a new pairwise DID Exchange connection has been accepted. Agent events are delivered to the controller as webhooks to a configured URL. More information on the administration API and webhooks can be found [here](https://github.com/hyperledger/aries-cloudagent-python/blob/master/AdminAPI.md).

## Resources

### Quickstart

If you are an experienced decentralized identity developer that knows Indy, are already familiar with the concepts behind Aries,  want to play with the code, and perhaps even start contributing to the project, an "install and go" page for developers can be found [here](https://github.com/hyperledger/aries-cloudagent-python/blob/master/DevReadMe.md).

### Architectural Deep Dive

The ACA-Py team presented an architectural deep dive webinar that can be viewed [here](https://youtu.be/FXTQEtB4fto). Slides from the webinar can be found [here](https://docs.google.com/presentation/d/1K7qiQkVi4n-lpJ3nUZY27OniUEM0c8HAIk4imCWCx5Q/edit#slide=id.g5d43fe05cc_0_77).

### Getting Started Guide

For everyone those new to SSI, Indy and Aries, we've created a [Getting Started Guide](https://github.com/hyperledger/aries-cloudagent-python/blob/master/docs/GettingStartedAriesDev/README.md) that will take you from knowing next to nothing about decentralized identity to developing Aries-based business apps and services in a hurry. Along the way, you'll run some early Indy apps, apps built on ACA-Py and developer-oriented demos for interacting with ACA-Py. The guide has a good table of contents so that you can skip the parts you already know.

### Read the Docs

The ACA-Py Python docstrings are used as the source of a [Read the Docs](https://aries-cloud-agent-python.readthedocs.io/en/latest/) code overview site. Want to review the
modules that make up ACA-Py? This is the best place to go.

### What to Focus On?

Not sure where your focus should be? Building apps? Aries? Indy? Indy's Blockchain? Ursa? Here is a [document](https://github.com/hyperledger/aries-cloudagent-python/blob/master/docs/GettingStartedAriesDev/IndyAriesDevOptions.md) that goes through the technical stack to show how the projects fit together, so you can decide where you want to focus your efforts.

## Credit

The initial implementation of ACA-Py was developed by the Verifiable Organizations Network (VON) team based at the Province of British Columbia. To learn more about VON and what's happening with decentralized identity in British Columbia, please go to [https://vonx.io](https://vonx.io).

## Contributing

Pull requests are welcome! Please read our [contributions guide](https://github.com/hyperledger/aries-cloudagent-python/blob/master/CONTRIBUTING.md) and submit your PRs. We enforce [developer certificate of origin](https://developercertificate.org/) (DCO) commit signing. See guidance [here](https://github.com/apps/dco).

We also welcome issues submitted about problems you encounter in using ACA-Py.

## License

[Apache License Version 2.0](https://github.com/hyperledger/aries-cloudagent-python/blob/master/LICENSE)

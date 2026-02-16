# CrossClient

The CrossClient facilitates interaction with the CROSS data platform with your 
Python routines. It allows to create and retrieve CrossContracts on/from the platform.
It further allows to submit and validate data to the platform. 

To use CrossClient you must be a registered user of the platform. You can register 
your account here: [Register User](https://sweet-cross.ch/register).


## Overview

The basic idea behind CrossClient is simple. It uses the API endpoints of the platform
to conveniently interact with it. It follows a resource-oriented design with three
main components:
- **CrossClient** The basic client to connect with the API. It handles authentication
and basic configurations.
- **Service** The service layer allows management of the basic objects. Most notably, the
`ContractService` allows to create, retrieve, and delete CrossContracts.
- **Resource** A resource is your local representation of an object stored at the CROSS
platform. The `ContractResource` is the representation of a CrossContract retrieved from 
the platform. It allows to inspect and manipulate the contract and to 
validate local data against the contract. Moreover, it allows to submit and retrieve 
data associated with the contract and saved at the CROSS platform.

The [tutorial](../notebooks/client_tutorial.ipynb) provides another overview of these basic principles with a code example.

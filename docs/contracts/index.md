# CrossContract

*CrossContracts* function as formal data contracts—documented agreements between data providers and consumers. They define the structure, quality, and expectations of physical data files to ensure seamless integration.

The contract serves as a logical blueprint of the data, primarily consisting of two pillars:

1. **Metadata**: This describes the data and also determines the operational metadata such as
ownership and versioning.

3. **Schema**: This defines the logical structure, including field names, data types (e.g., string, integer),
whether fields are mandatory or optional, and further constraints (minimum, maximum etc.). Moreover, schemas
contain also some semantic data describing the fields.

The package is build in a way, that [Metadata](metadata.md) are flexible. For *CrossContracts*
the metadata are determined by the CROSS-Team. The package, however, allows to formulate [contracts with a custom set of metadata entries] (see contracts/custom_metadata.md).

<!-- They follow the [DCAT-CH v.2](https://www.dcat-ap.ch/)
to be compliant with the [Swiss Open Government Data approach](https://www.bfs.admin.ch/bfs/en/home/services/ogd.html). -->


[Schemas](schema.md) describe tabular data resources and implement the [frictionless table
standard](https://specs.frictionlessdata.io//table-schema/). The schemas in this
package however enhance the frictionless standard introducing field descriptors
that allow to impose further semantic information and unit information.

The data contracts in this packages only describe the logical content of data. They,
however, do not impose any restrictions on the file format in which the physical data
are provided. A contract describes the content but data can be in csv, json, parquet,
or any other data format.

Summarizing, the data contracts in this package harmonize the way to describe data
such that data consumers have all information available to use the data. For data
providers the contracts allow to validate physical data against the contract. They
can therefore test, that the delivered data comply with the contact.

What is the role of the CROSS platform for the data contracts in this packages. In
short, the data contracts do not rely at all on the CROSS platform. Contracts can be
used independently of the platform. The platform itself, however, also uses this
package. The platform allows to store and retrieve contracts from a central location.
It further allows to submit data for a given contract and ensures that the data
submitted comply with the contract. The [CrossClient](../client/index.md) facilitates
using contracts together with the platform. Contracts can however be used for bilateral
exchange or also with another platform.



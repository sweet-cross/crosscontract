# Schemas

*CrossContract* currently deals only with tabular data but is designed to allow to
extend to other data types.

## Table schemas

A table schema is a description of each field/column
in the data specifying the data type, the semantic meaning of the column, as well as
additional constraints on the data (e.g., minimum, maximum, ...). The currently
available field are (check the API references for the most updated versions).

| Field | Description | Constraints |
| --- | --- | --- |
| IntegerField | Restricts type to be an integer number | minimum, maximum, enum |
| FloatField | Restricts type to be float number | minimum, maximum, enum |
| StringField | Restricts type to a string | minLength, maxLength, pattern, enum | 
| DateTimeField | Restricts type to a valid datetime with a given format | minimum, maximum, enum | 
| ListField | Restricts type to a valid list of a certain item type | minLength, maxLength | 



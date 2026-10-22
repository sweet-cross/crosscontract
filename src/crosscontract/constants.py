# A deliberately strict subset of the Frictionless identifier pattern
# (``^([-a-z0-9._/])+$``, see `FRICTIONLESS_NAME_PATTERN` in
# `_standards.frictionless`): lowercase alphanumeric characters plus '.', '_', and
# '-'. The '/' the standard permits is intentionally excluded. Because this is a
# subset, any accepted name is also a valid Frictionless name, so contracts stay
# release-compliant by construction.
CONTRACT_NAME_PATTERN = r"^([-a-z0-9._])+$"

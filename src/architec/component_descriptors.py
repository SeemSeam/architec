from ._compat_reexport import reexport

reexport(__package__ or "architec", ".descriptors.public", globals())

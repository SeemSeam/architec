from ._compat_reexport import reexport

reexport(__package__ or "architec", ".scoring.public", globals())

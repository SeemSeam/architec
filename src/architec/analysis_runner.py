from ._compat_reexport import reexport

reexport(__package__ or "architec", ".analysis.public", globals())

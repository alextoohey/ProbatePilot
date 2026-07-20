"""Persistence backends for ProbatePilot.

`kv` holds the uniform get/set/delete/scan interface shared by all three
supported backends. Vector search differs enough per provider (Upstash
Vector's REST index vs. Redis 8's VADD/VSIM commands vs. an in-process cosine
scan) that each gets its own module instead of being forced through a shared
abstraction.
"""

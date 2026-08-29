"""Domain and infrastructure reconnaissance beyond what a crawl can reveal.

* :mod:`domain` — registration, DNS, hosting and ASN, country, and TLS;
* :mod:`cdn` — the CDN in front of a site and observed cache behavior;
* :mod:`tech` — CMS, frameworks, analytics, pixels, and widgets;
* :mod:`security` — security headers and publicly exposed service files;
* :mod:`backlinks` — whether known donor links are live and pass ranking signals.

Every function returns a JSON-compatible dictionary. Network failures are
reported as result data rather than raised to callers.
"""

__all__ = ["backlinks", "cdn", "domain", "security", "tech"]

# HTTPS data import and English installer

Reuse export-data/migrate-data/verify-data. Add a verified data-package.json release
asset (HTTPS URL, SHA-256, byte size) and stream a verified flat package
into a private cache. Ask “Import data?” immediately after PostgreSQL preparation.
Keep explicit local packages and noninteractive commands. The descriptor is separate
from release-manifest.json, avoiding a circular archive/manifest checksum.

Use concise English prompts/errors. Record internal progress in a private log.
Initial scope excluded VPS, source database, push or release changes. On completion,
the user authorized branch push and RC publication, then a brief local application
pause for a private complete source export with restart. No main merge, VPS deploy
or source data publication is authorized. Tests cover corrupt downloads,
unsafe archives/redirects, retries, both database selections and unchanged data guards.

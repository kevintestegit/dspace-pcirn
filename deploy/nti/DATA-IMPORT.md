# Optional data import

Run `sudo dspacepcirn`, select **Install DSpace**, then choose the database:

```text
1. Managed PostgreSQL (Docker)
2. Existing PostgreSQL
Choice [1]:

Import data? [y/N]:
```

**No** initializes an empty repository, using a release with fresh bootstrap support.
**Yes** downloads the selected release's data package and verifies it before restore.
The same import runs against either database mode. Existing databases with user
objects are refused. No import overwrites an initialized repository.

Normal output shows one line per stage. Internal progress is written to the private
`/srv/dspacepcirn/installer.log`; errors retain the checkpoint and diagnostic report.
Local packages still work with `--data-package DIRECTORY`. Noninteractive commands
keep their explicit arguments and never fetch data without selecting an import.

## Prepare and host a package

The release maintainer prepares the package once; administrators do not enter URLs,
hashes, PostgreSQL commands or download credentials during installation.

1. Export the source using `export-data` during an authorized maintenance window.
   Export stops its own stack and leaves it stopped. The source must use the exact
   target release, including its manifest and database profile.
2. Wrap the completed export with the existing checksum files:

   ```bash
   python3 scripts/package-data.py \
     --package /transfer/export \
     --url https://downloads.example.org/rc5-data.tar.gz \
     --output /transfer/rc5-data.tar.gz
   ```

   This creates the archive and `rc5-data.tar.gz.json` (URL, SHA-256, byte size).
   Existing output is never overwritten.
3. Upload the archive to an HTTPS file server, object storage, or a Drive direct
   download link. The installer supports public file downloads, not preview pages,
   interactive login, Drive confirmation forms or arbitrary remote scripts.
4. Attach the generated JSON to the **matching official GitHub release** as
   `data-package.json`. Its GitHub asset SHA-256 must be available. The installer
   verifies both the official descriptor and the archive downloaded from its URL.

The descriptor is a separate release asset; it does not change `release-manifest.json`
and avoids making an archive checksum depend on itself. A release without the asset
cannot offer automatic import. Change releases when changing the dataset: retries
pin the original descriptor and reuse only verified cached files.

The flat archive contains exactly `database.dump`, `assetstore.tar.gz`, `solr.tar.gz`,
`source-report.json`, `release.json` and `checksums.json`. A raw SQL or PostgreSQL dump
alone is insufficient: documents and Solr statistics must travel with the database.
Private-address redirects, HTTP, symlinks, unexpected paths, corruption, insufficient
disk space and incompatible release/profile are refused before restoration.

Public hosting is suitable for fictitious demonstration data. Institutional exports
contain user and repository data; publish them only with explicit authorization.
No data package or public URL is bundled with this implementation yet.

## Existing local Docker installation

For an existing installation that predates the manager, the maintainer can use:

```bash
python3 scripts/export-docker-data.py \
  --manifest /private/release-manifest.json \
  --output /private/new-export
```

This explicitly selected source uses the local default Docker Unix endpoint.
It checks the complete institutional Flyway history against the manifest before
stopping the selected backend, frontend and Solr. PostgreSQL stays running.
Queries and the dump use PostgreSQL clients inside its container over a verified
Unix socket; no host server, TLS settings or database credentials are changed.
The helper copies documents and statistics, fingerprints every table and file,
validates the dump, and always attempts to restart all stopped source services.
The operator must confirm application health afterward. Partial exports and
private working copies are retained for inspection; existing outputs are refused.

The export is private and does not publish data. Its manifest identifies the
intended import release, whose entire history must match the source exactly.
Use that release when importing; do not manually replace the export's manifest.

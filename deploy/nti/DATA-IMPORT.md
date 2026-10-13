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

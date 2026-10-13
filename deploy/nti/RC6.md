# RC6 delivery

This candidate adds automatic Ubuntu dependencies, release discovery, managed or
external PostgreSQL, verified empty bootstrap, optional HTTPS data import and a
concise English interface. Existing noninteractive commands remain available.

Publication uses the isolated `feat/automated-installer` branch, without merging
main. The release pipeline checks the installer with a real disposable PostgreSQL
15 and runs backend unit tests. Each native AMD64/ARM64 backend build must prove
empty PostgreSQL 16 bootstrap, repeat initialization, Flyway validation and refusal
of existing data before image tags are published. Measured history must match the
release history. Candidate releases are explicitly marked as prereleases.

The release contains immutable multiarchitecture image references, the release
manifest and the manager archive with its checksum. Data is a separate optional
asset; publishing software does not publish repository data.

Local validation: 229 installer tests passed, including the PostgreSQL 15
export/restore test. The public test certificate has explicit read permission so
the test also works after other tests set umask 077; its private key stays private.
Log: `/tmp/pcirn-rc5-final-installer.log`.

The RC5 publication gate found six fixture errors on GitHub: simulated PostgreSQL
commands were accidentally combined with real client directories from the runner.
No RC5 images or release were published. The fixture now isolates that lookup and
explicitly tests selection of the exact-major directory. RC6 keeps the gate enabled.
After this fix and the private source export helper, 236 tests passed, followed by
seven focused export tests after pinning its local Docker endpoint.
Log: `/tmp/pcirn-rc6-installer.log`.

## Private source export

The user authorized a brief local application pause and private export. The helper
exported `/home/gecid007/dspacepcirn-private-exports/source-20261013` against the
verified RC4 manifest: the source's 87 Flyway entries match it exactly. No source
migration or database setting was changed. Backend, frontend and Solr were restarted
and all three returned healthy; PostgreSQL remained running throughout.

The copy contains 65 tables, 2,256 items, 4 users, 6,830 bitstream records, 6,759
verified live documents, 6,830 assetstore files and 402 Solr files. A separate
PostgreSQL 15 container, without networking, restored the real dump and reproduced
the complete report: all table fingerprints and document/statistics fingerprints
matched. The disposable verification container was stopped and retained.

The flat directory and transfer archive are private (directory 700, files 600).
Archive: `/home/gecid007/dspacepcirn-private-exports/source-20261013.tar.gz`,
520,854,702 bytes, with a separate SHA-256 file. Proof:
`/home/gecid007/dspacepcirn-private-exports/restore-proof.json`.
No data was uploaded, committed or published. This package is tied to RC4; it must
not be passed to RC6 or relabeled manually. A package for another release must be
prepared with a matching verified manifest/history. Hosting and data publication
remain separate from software release publication.

The earlier GitHub Build for this branch passed unit tests and failed API
integration tests (S3 mock bucket/HTTP errors and a teardown concurrent modification).
Log: `/tmp/pcirn-rc5-build-failure.log`; run 38420781722. No S3 or Context code was
changed in this installer branch, and these failures were not suppressed.

Remaining acceptance checks: installation from a clean Ubuntu 24.04 VM with
systemd, the full stack on ARM64, and an authorized hosted data package.
The Oracle VPS is not a disposable test environment and deployment there
remains paused. The preexisting REST integration failures recorded in AUTOMACAO.md
remain disclosed; publication does not claim the entire Maven integration suite
passes.

## Published release and full stack

[RC6](https://github.com/kevintestegit/dspace-pcirn/releases/tag/v1.0.0-rc6) was
published as a prerelease from `45bdcc9f8493569bd3d2f18f1821411aeadb06f9`.
[Publication run](https://github.com/kevintestegit/dspace-pcirn/actions/runs/38421955489)
passed the 237 installer tests, Maven unit gate, all six native image builds and
empty bootstrap on AMD64 and ARM64. Both backends reproduced 79 migration checksums,
resumed initialization and rejected existing/incompatible data. The manager's
automatic discovery selected RC6 and independently verified the assets and both
platforms for every image.

- Manifest SHA-256: `5a037d1a2233bafbf7b03b487a8cdfb483076671bea9e00bd6828b61e1761d36`.
- Manager SHA-256: `03da3082d110da6029f651645e43f5b32d3b8e97d4e5a528347cbc8e6087526c`.
- Proof: `/home/gecid007/dspacepcirn-release-proof-rc6/verified-release.json`.

The published manager ran the complete empty installation in an isolated Ubuntu
24.04 runner with its own PostgreSQL16, network, ports and persistent storage.
REST and Angular returned HTTP200; all three services were healthy. PostgreSQL
used TLS and a NOSUPERUSER role; no items, communities, collections or users were
seeded. Repeating the wizard preserved the 79-entry history. A missing Docker
storage mount in the runner caused an initial preflight failure; after correcting
the test mount, the saved checkpoint resumed with identical password and TLS files.
This proves container-based Ubuntu operation, not a fresh systemd host installation.
Proof: `/home/gecid007/dspacepcirn-release-proof-rc6/full-stack-proof.json`.

After publication, the authorized private exporter produced a second complete
copy against the verified RC6 manifest, checking the same 87 institutional
migrations before its brief source pause. The original services returned healthy.
The RC4 copy remains intact; neither copy was relabeled or uploaded.

RC6 archive: `/home/gecid007/dspacepcirn-private-exports/source-rc6-20261013.tar.gz`,
520,857,085 bytes, SHA-256
`3b97490757c3c625429e71d62b919b7b343c9664749a0f8dee9e8e6a146e005d`.
Directory: `/home/gecid007/dspacepcirn-private-exports/source-rc6-20261013`.

The published migration wizard restored this real package into another dedicated
PostgreSQL16 with TLS and a NOSUPERUSER role, in Ubuntu24.04. All 65 table
fingerprints matched after application startup (2,256 items and preserved UUIDs,
handles, users, permissions and 87 Flyway records). Assetstore fingerprints matched;
the complete Solr restore was verified before services started. Backend, Angular
and Solr were healthy, with REST and frontend HTTP200. Both disposable stacks were
stopped; containers, volumes, files and backups were retained.
Proof: `/home/gecid007/dspacepcirn-release-proof-rc6/data-stack-proof.json`.
Logs: `/tmp/pcirn-rc6-full-stack-resume.log` and
`/tmp/pcirn-rc6-real-data-stack.log`.

Automatic data download remains pending: the exact archive contains user and
repository data and has no authorized hosting URL or `data-package.json` asset.
Local import uses the matching RC6 directory. Source data was not committed or
published. There was no main merge or VPS deployment during this delivery.

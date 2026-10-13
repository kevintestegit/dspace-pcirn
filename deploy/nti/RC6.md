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

Remaining acceptance checks: native CI results, installation from a clean Ubuntu
24.04 VM with systemd, complete backend/Angular/Solr health, and a hosted data
package. The Oracle VPS is not a disposable test environment and deployment there
remains paused. The preexisting REST integration failures recorded in AUTOMACAO.md
remain disclosed; publication does not claim the entire Maven integration suite
passes.

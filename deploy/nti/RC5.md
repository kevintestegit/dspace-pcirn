# RC5 delivery

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

Remaining acceptance checks: native CI results, installation from a clean Ubuntu
24.04 VM with systemd, complete backend/Angular/Solr health, and a hosted data
package. The Oracle VPS is not a disposable test environment and deployment there
remains paused. The preexisting REST integration failures recorded in AUTOMACAO.md
remain disclosed; publication does not claim the entire Maven integration suite
passes.

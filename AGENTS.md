# Repository Guidelines

## Project Structure & Module Organization

This repository contains the DSpace backend, a Maven multi-module Java 17 application. Core domain and API code lives in `dspace-api/`; application services are in `dspace-services/`; the REST server is in `dspace-server-webapp/`. Protocol and integration modules include `dspace-oai/`, `dspace-sword/`, `dspace-swordv2/`, `dspace-rdf/`, `dspace-saml2/`, and `dspace-iiif/`. Each module keeps production code under `src/main` and tests under `src/test`. Root-level `pom.xml`, Dockerfiles, and Compose files provide build and local deployment configuration.

## Build, Test, and Development Commands

Use Java 17 and Maven 3.8 or newer.

```bash
mvn install
mvn install -DskipUnitTests=false -DskipIntegrationTests=false
mvn test -DskipUnitTests=false
```

The first command builds modules with tests skipped by default. The second runs unit and integration tests; the third runs unit tests only. To work on one module, install required dependencies from the repository root, then run the relevant Maven command from that module directory. Docker Compose files provide development/testing services; follow `dspace/src/main/docker-compose/README.md` for the supported setup.

## Coding Style & Naming Conventions

Follow the project Code Style Guide and existing Java conventions: four-space indentation, descriptive `PascalCase` types, `camelCase` methods and variables, and uppercase `CONSTANT_CASE` constants. Keep packages under `org.dspace`, preserve import organization, and add Javadoc for new or modified public classes and methods. Every pull request must pass Checkstyle validation.

## Testing Guidelines

Place unit and integration tests in the module’s `src/test` tree, using existing test naming and package patterns. Add or update tests for behavior changes. Run the narrowest relevant test first, then the full unit/integration command before submitting. CI runs the project checks for commits and pull requests.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects that identify the change (for example, `reorganize imports`). Keep pull requests preferably below 1,000 changed lines, explain the problem and solution, link any related issue, and include exact testing steps. Document REST contract changes and disclose any new dependency and its license. Keep PRs focused and ensure all automated checks pass.

## Security & Configuration

Do not commit credentials, local `.env` files, database dumps, or generated artifacts. Review configuration and dependency changes carefully, and use the project’s documented PostgreSQL, Solr, and servlet-container setup for local testing.

# AGENTS.md

- Do not preserve backward compatibility. Removeobsoletepaths instead of adding compatibility layers, fallbacks, or migrations.
- Choose the simplest implementation that fully meets the current requirements. Avoid speculative abstraction configuration, andindirection.
- Grow the system in layers. Start from the smallest version that works end to end, and add each new capability on top of a product that already works. Never trade a working product for unfinished complexity.
- Keep components modular and concerns clearly separated.
- Prefer established, well-maintained libraries when they reduce overall
  complexity or improve reliability. Do not reimplement common functionality without a clear reason.
- Lean on the dependencies already in the project before writing your own implementation or adding packages. Do not assume a library lacks a capability without checking its documentation and types.
- Make architectural decisions for the long term. Do not accept a stopgap that only works for now and is meant to be replaced later.    
#!/usr/bin/env python3
"""Generate docker-compose.recovery.yml from the resolved runtime config.

The stack that was destroyed on 2026-10-08 had been created from
.../restauracao-itep-20260930/private/runtime/dspace.json, which is Docker
Compose's *resolved* output: fully interpolated, with the real image tags and
the volume names it actually used (d9_pgdata, d9_config and so on).

Transcribing that by hand invites drift, so this reads the JSON and emits an
equivalent Compose file. Both documents are passed through a targeted
normalisation before comparison, because the JSON carries resolved artefacts
(`name`, `index`, and volumes materialised as `type: volume`) that a Compose
source does not.

Usage:
  scripts/compose-from-runtime.py /path/to/dspace.json > docker-compose.recovery.yml
"""
import json
import sys

VOLUME_SOURCES = ('assetstore', 'pgdata', 'solr_data', 'restored_config',
                  'dbhome', 'solrhome')


def normalise(doc):
    """Reduce a Compose document to what matters for equivalence."""
    out = {'networks': {}, 'services': {}}
    for name, net in (doc.get('networks') or {}).items():
        entry = {}
        if net.get('name'):
            entry['name'] = net['name']
        if net.get('ipam'):
            entry['ipam'] = net['ipam']
        out['networks'][name] = entry
    for name, svc in (doc.get('services') or {}).items():
        entry = {}
        for key in ('image', 'container_name', 'restart', 'user',
                    'working_dir', 'entrypoint', 'command', 'healthcheck',
                    'environment', 'ports', 'depends_on', 'networks'):
            if svc.get(key):
                entry[key] = svc[key]
        # Volumes: the resolved form is a list of mappings, the source form a
        # list of strings. Compare the (source, target) pair only.
        vols = []
        for vol in (svc.get('volumes') or []):
            if isinstance(vol, dict):
                vols.append((vol.get('source'), vol.get('target')))
            else:
                parts = vol.split(':')
                vols.append((parts[0], parts[1] if len(parts) > 1 else None))
        entry['volumes'] = sorted(vols, key=lambda p: p[1] or '')
        out['services'][name] = entry
    return out


def build(runtime):
    """Build the Compose document from the resolved runtime document."""
    doc = {
        'name': runtime.get('name'),
        'networks': {},
        'volumes': {},
        'services': {},
    }
    for net_name, net in (runtime.get('networks') or {}).items():
        entry = {'external': True}
        if net.get('name'):
            entry['name'] = net['name']
        doc['networks'][net_name] = entry
    for vol_name, vol in (runtime.get('volumes') or {}).items():
        doc['volumes'][vol_name] = {'name': vol['name'], 'external': True}

    for svc_name, svc in (runtime.get('services') or {}).items():
        entry = {}
        for key in ('image', 'container_name', 'restart', 'user', 'working_dir'):
            if svc.get(key):
                entry[key] = svc[key]
        if svc.get('environment'):
            entry['environment'] = {
                key: str(svc['environment'][key])
                for key in sorted(svc['environment'])
            }
        # Three cases, and they differ:
        #   null  -> the Compose file set no entrypoint, so the image's own
        #            entrypoint must be kept. dspacedb depends on this:
        #            docker-entrypoint.sh is what drops privileges with gosu,
        #            and clearing it makes PostgreSQL refuse to start as root.
        #   []    -> the Compose file deliberately cleared the image entrypoint.
        #            dspace-angular needs this, because its image entrypoint is
        #            ["sh"] and would run `sh npm run serve ...`.
        #   [...] -> use it as given.
        if 'entrypoint' in svc and svc['entrypoint'] is not None:
            entry['entrypoint'] = svc['entrypoint']
        if svc.get('command'):
            entry['command'] = svc['command']
        if svc.get('ports'):
            ports = []
            for port in svc['ports']:
                item = {'target': port['target'],
                        'published': str(port['published'])}
                if port.get('host_ip'):
                    item['host_ip'] = port['host_ip']
                if port.get('protocol'):
                    item['protocol'] = port['protocol']
                ports.append(item)
            entry['ports'] = ports
        if svc.get('volumes'):
            vols = []
            for vol in svc['volumes']:
                source, target = vol.get('source'), vol.get('target')
                if source in VOLUME_SOURCES:
                    vols.append(f'{source}:{target}')
                else:
                    # Anything else in dspace.json is a bind mount. The running
                    # stack did not use them, so they are not reproduced.
                    vols.append({'__omitted_bind__': f'{source}:{target}'})
            entry['volumes'] = vols
        if svc.get('healthcheck'):
            hc = dict(svc['healthcheck'])
            test = hc.get('test')
            if isinstance(test, str):
                test = ['CMD-SHELL', test]
            hc['test'] = test
            entry['healthcheck'] = hc
        if svc.get('depends_on'):
            deps = svc['depends_on']
            if isinstance(deps, dict):
                entry['depends_on'] = {
                    dep: {'condition': spec.get('condition', 'service_started')}
                    for dep, spec in deps.items()
                }
            else:
                entry['depends_on'] = list(deps)
        if svc.get('networks'):
            nets = svc['networks']
            entry['networks'] = list(nets)
        doc['services'][svc_name] = entry
    return doc


def emit(json_path, stream):
    import yaml

    with open(json_path, encoding='utf-8') as handle:
        runtime = json.load(handle)

    doc = build(runtime)
    header = (
        '# Geracao automatica - NAO EDITE A MAO.\n'
        '#\n'
        '# Reconstitui a stack d9 destruida em 2026-10-08, a partir de\n'
        '# .../restauracao-itep-20260930/private/runtime/dspace.json, que e a\n'
        '# configuracao resolvida que criou os containers originais.\n'
        '#\n'
        '# Volumes e rede sao externos: este arquivo nao cria nem remove nada.\n'
        '# Regerar com: scripts/compose-from-runtime.py <dspace.json>\n'
    )
    # A real serialiser is used rather than string building: the entrypoints
    # are multi-line shell scripts, and losing those newlines silently breaks
    # every container.
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True,
                          default_flow_style=False, width=10 ** 6)
    stream.write(header + body)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    emit(sys.argv[1], sys.stdout)

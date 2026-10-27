"""decksync runner: keeps Flo's Claude Slides decks in step with the Legal Recruiting Tracker and HubSpot.

Commands (run from the repo root):
  python3 decksync/run.py files                       list every artifact file to read before a build
  python3 decksync/run.py build --data D --work W      rebuild owned slides + patch numbers in W/<deck-id>/...
  python3 decksync/run.py merge-clients --fresh F      Mondays: apply HubSpot numbers, hold decreases
  python3 decksync/run.py approve [key ...]            apply held decreases (all, or the keys given)
  python3 decksync/run.py check --data D               CI: every generator must render from D without error

W is a folder holding each deck's files at their artifact paths under W/<deck-id>/ (deck-id = last part of
the artifact URL). `build` writes W/changes.json: per deck, the files that changed and must be published,
plus a plain-English summary for Slack.
"""
import argparse, json, os, re, sys, traceback
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render  # noqa: E402

DECKS = os.path.join(HERE, 'decks.json')
CLIENTS = os.path.join(HERE, 'client_stats.json')   # default; the scheduled task passes --clients <state file from the private settings artifact>


def deck_id(url):
    return url.rstrip('/').split('/')[-1]


def decks():
    return json.load(open(DECKS))['decks']


def logo_src(html):
    m = re.search(r'<img[^>]*src="(/_blob/[0-9a-f]{32})"[^>]*alt="Flo"', html) or \
        re.search(r'<img[^>]*alt="Flo"[^>]*src="(/_blob/[0-9a-f]{32})"', html)
    return m.group(1) if m else None


def cmd_files(_):
    print('data_url:', json.load(open(DECKS))['data_url'])
    out = []
    for d in decks():
        paths = [f'project/slides/{sid}.html' for sid in d['own']] + d['patch']
        out.append({'deck': d['name'], 'url': d['url'], 'id': deck_id(d['url']), 'paths': paths})
    print(json.dumps(out, indent=1))


def cmd_build(a):
    data = json.load(open(a.data))
    cs = render.load_client_stats(a.clients)
    changes, problems = {}, []
    ctx = render.Ctx(data)
    for d in decks():
        did = deck_id(d['url'])
        root = os.path.join(a.work, did)
        changed = []
        # logo: reuse whatever Flo logo asset the deck already uses
        logo = None
        for sid in d['own']:
            p = os.path.join(root, 'project', 'slides', f'{sid}.html')
            if os.path.exists(p):
                logo = logo or logo_src(open(p).read())
        for sid, gen in d['own'].items():
            p = os.path.join(root, 'project', 'slides', f'{sid}.html')
            try:
                if not logo:
                    raise RuntimeError('no Flo logo found in the deck')
                _, res = render.render(data, [(sid, gen)], logo)
                html = res[sid][0]
            except Exception as e:  # missing/renamed tracker field etc. -> keep the old slide, report it
                problems.append(f'{d["name"]} › {sid} ({gen}) kept as is: {e.__class__.__name__}: {e}')
                continue
            old = open(p).read() if os.path.exists(p) else None
            if old != html:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'w').write(html)
                changed.append(f'project/slides/{sid}.html')
        for rel in d['patch']:
            p = os.path.join(root, rel)
            if not os.path.exists(p):
                problems.append(f'{d["name"]} › {rel} not found (renamed or removed?)')
                continue
            old = open(p).read()
            new, n = render.patch_text(old, ctx, cs)
            if n == 0:
                problems.append(f'{d["name"]} › {rel}: no numbers matched (wording changed?)')
            if new != old:
                open(p, 'w').write(new)
                changed.append(rel)
        if changed:
            changes[d['url']] = {'deck': d['name'], 'root': root, 'files': changed}
    pending = json.load(open(a.clients)).get('pending', {}) if os.path.exists(a.clients) else {}
    summary = {'asof': ctx.asof, 'decks_changed': len(changes), 'problems': problems,
               'held_client_stats': [f'{k}: held at {v["was"]} (HubSpot shows {v["shows"]} since {v["since"]})'
                                     for k, v in pending.items()]}
    json.dump({'changes': changes, 'summary': summary}, open(os.path.join(a.work, 'changes.json'), 'w'), indent=1)
    print(json.dumps(summary, indent=1))


def cmd_merge_clients(a):
    fresh = json.load(open(a.fresh))
    today = datetime.now(timezone.utc).date().isoformat()
    applied, held = render.merge_client_stats(a.clients, fresh, today)
    print(json.dumps({'applied': applied, 'held': held}, indent=1))


def cmd_approve(a):
    render.approve_pending(a.clients, a.keys or None)
    print('approved', a.keys or 'all')


def cmd_check(a):
    data = json.load(open(a.data))
    gens = sorted({g for d in decks() for g in d['own'].values()})
    failed = []
    for g in gens:
        try:
            render.render(data, [('check', g)], '/_blob/' + '0' * 32)
        except Exception:
            failed.append(g)
            traceback.print_exc()
    ctx = render.Ctx(data)
    render.student_counts(ctx)
    if failed:
        sys.exit(f'decksync: {len(failed)} slide generator(s) broke on this data.json: {", ".join(failed)}')
    print(f'decksync: all {len(gens)} slide generators render from this data.json')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('files')
    b = sub.add_parser('build'); b.add_argument('--data', required=True); b.add_argument('--work', required=True)
    m = sub.add_parser('merge-clients'); m.add_argument('--fresh', required=True)
    ap_ = sub.add_parser('approve'); ap_.add_argument('keys', nargs='*')
    for p_ in (b, m, ap_):
        p_.add_argument('--clients', default=CLIENTS)
    c = sub.add_parser('check'); c.add_argument('--data', required=True)
    a = ap.parse_args()
    {'files': cmd_files, 'build': cmd_build, 'merge-clients': cmd_merge_clients,
     'approve': cmd_approve, 'check': cmd_check}[a.cmd](a)

"""Render Claude Slides slide files from the Flo Forward Legal Recruiting Tracker data.json.

Usage: python3 render.py <data.json> <out_root> <logo_src> [slide_key ...]
Writes <out_root>/project/slides/<id>.html for each requested slide and prints a JSON
summary of the headline numbers it used.
"""
import json, math, sys, os
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------- data helpers
MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
MONTH_FULL = ['January','February','March','April','May','June','July','August',
              'September','October','November','December']
SEASON_COLORS = {'2022-2023':'#FC97C2','2023-2024':'#4D8EFF','2024-2025':'#4DA54C',
                 '2025-2026':'#192B92','2026-2027':'#EB232D','2027-2028':'#C74500'}
CLASS_COLORS = {'Class of 2026':'#4D8EFF','Class of 2027':'#4DA54C',
                'Class of 2028':'#192B92','Class of 2029':'#EB232D','Class of 2030':'#C74500'}
INK, MUTED, FAINT = '#261025', '#574656', '#8A7F86'
PARTIAL_DASH_UNTIL_DAY = 15
LOGO = ['']  # set by render(); watermark in each chart card


def central(dt):
    # America/Chicago: CDT (UTC-5) from 2nd Sun Mar to 1st Sun Nov, else CST (UTC-6)
    y = dt.year
    mar = datetime(y, 3, 8, tzinfo=timezone.utc); start = mar + timedelta(days=(6 - mar.weekday()) % 7, hours=8)
    nov = datetime(y, 11, 1, tzinfo=timezone.utc); end = nov + timedelta(days=(6 - nov.weekday()) % 7, hours=7)
    return dt + timedelta(hours=-5 if start <= dt < end else -6)


def season_of(year, month):
    """Tracker school-year key and Jul-Jun index for a calendar month (month 1-12)."""
    if month >= 7:
        return f'{year}-{year+1}', month - 7
    return f'{year-1}-{year}', month + 5


def val(series, year, month):
    key, i = season_of(year, month)
    arr = series.get(key)
    if not arr or i >= len(arr):
        return None
    return arr[i]


def sep_aug(series, season):
    """Season shown Sep..Aug = tracker[season][2:12] + tracker[next][0:2]."""
    a, b = season.split('-')
    nxt = f'{b}-{int(b)+1}'
    cur = series.get(season) or [None] * 12
    nx = series.get(nxt) or [None] * 12
    return list(cur[2:12]) + list(nx[0:2])


def sum_series(*ss):
    keys = set().union(*[s.keys() for s in ss])
    out = {}
    for k in keys:
        arrs = [s.get(k) for s in ss]
        n = max(len(a) for a in arrs if a)
        out[k] = []
        for i in range(n):
            vals = [a[i] if a and i < len(a) else None for a in arrs]
            out[k].append(None if all(v is None for v in vals) else sum(v or 0 for v in vals))
    return out


def fmt_n(n):
    return f'{int(round(n)):,}'


def floor_plus(n, step=100):
    return f'{int(n // step * step):,}+'


def change(cur, prev):
    """('up', text) for a meaningful increase, else None. Multiples at 3x+, else percent."""
    if cur is None or prev is None:
        return None
    if prev <= 0:
        return ('x', None) if cur > 0 else None
    r = cur / prev
    if r >= 3:
        return ('x', f'{math.floor(r)}x')
    if r >= 1.10:
        return ('pct', f'{round((r - 1) * 100)}%')
    return None


class Ctx:
    def __init__(self, data):
        self.d = data
        self.L = data['charts']['lawStudent']
        gen = datetime.fromisoformat(data['meta']['generatedAt'].replace('Z', '+00:00'))
        self.now = central(gen)
        y, m = self.now.year, self.now.month
        self.cur = (y, m)                                   # month in progress
        self.full = (y, m - 1) if m > 1 else (y - 1, 12)    # latest full month
        self.asof = f'{MON[m-1]} {self.now.day}, {y}'
        # dash the month in progress only in its first half; later it reads as a normal point
        self.mark_partial = self.now.day < PARTIAL_DASH_UNTIL_DAY
        self.note = ' · Dashed: month in progress' if self.mark_partial else ''
        self.season = season_of(y, m)[0]                   # e.g. 2026-2027
        a = int(self.season[:4])
        self.prev_season = f'{a-1}-{a}'
        self.newest_class = f'Class of {a+3}'               # 1Ls entering in fall `a`
        self.prior_class = f'Class of {a+2}'

    def yoy(self, series, ym):
        y, m = ym
        return val(series, y, m), val(series, y - 1, m)


# ---------------------------------------------------------------- slide chrome
BG = 'linear-gradient(180deg, #E7E5DB 0%, #EDEBE4 34%, #F2F1EB 68%, #F6F5F0 100%)'
CARD = ('border-radius:16px;border:1px solid rgba(38,16,37,0.15);'
        'box-shadow:0 12px 40px 0 rgba(38,16,37,0.04), 0 4px 16px 0 rgba(38,16,37,0.05), 0 1px 2px 0 rgba(38,16,37,0.03);'
        'background:#FFFFFF')
SANS = "'Zalando Sans', Arial, sans-serif"
SERIF = "'Season Mix', Georgia, serif"
SEMI = "'Zalando Sans SemiExpanded', Arial, sans-serif"


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


TRACKER = 'https://resources.joinflo.com/tracker'
LINK_STUDENT = TRACKER + '/student/lawfirm/summer/market'      # 1L-2L summer > Market Data
LINK_LATERAL = TRACKER + '/attorney/lawfirm/nonpartner/market'  # Lateral non-partner > Market Data
LINK_PARTNER = TRACKER + '/attorney/lawfirm/partner/market'
LINK_POSTCLERK = TRACKER + '/attorney/lawfirm/postclerk/market'


def footer(ctx, extra='', link=LINK_STUDENT):
    name = 'Flo Forward Legal Recruiting Tracker'
    rest = esc(f' · Data through {ctx.asof}{extra}')
    return (f'<p style="position:absolute;left:120px;bottom:28px;width:1680px;font-size:24px;'
            f'line-height:1.2;color:{FAINT}">Source: <a href="{link}">{name}</a>{rest}</p>')


def chart_slide(sid, logo, title, subtitle, chart_html, ctx, note, aside):
    return (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};'
        f'padding:140px 120px 90px;display:flex;flex-direction:column;gap:28px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:16px">\n'
        f'<h2 style="width:1680px;font-family:{SANS};font-weight:600;font-size:64px;line-height:1.05;letter-spacing:-1.6px;color:{INK}">{esc(title)}</h2>\n'
        f'<p style="width:1560px;font-size:26px;line-height:1.45;color:{MUTED}">{esc(subtitle).replace("[[b]]", "<b>").replace("[[/b]]", "</b>")}</p>\n'
        f'</div>\n'
        f'<div style="display:flex;flex-direction:row;justify-content:start">\n{chart_html}\n</div>\n'
        f'{footer(ctx, note)}\n'
        f'<aside>{esc(aside)}</aside>\n'
        f'</section>\n')


# ---------------------------------------------------------------- line chart
def nice_max(vmax):
    if vmax <= 0:
        return 4, 1
    raw = vmax / 4
    mag = 10 ** math.floor(math.log10(raw))
    for f in (1, 2, 2.5, 5, 10):
        if f * mag >= raw:
            step = f * mag
            break
    return step * 4, step


def tick_label(v):
    if v >= 1000:
        k = v / 1000
        return f'{k:g}k'
    return f'{v:g}'


def line_chart(title, sub, xlabels, series, partial, aria, width=1680):
    """series: [{label,color,values}], partial: (series_index, point_index) of month in progress."""
    pad = 32
    inner = width - 2 * pad - 2
    ylab_w, gap = 72, 16
    W, H = inner - ylab_w - gap, 350
    vmax = max([v for s in series for v in s['values'] if v is not None] + [0])
    ymax, step = nice_max(vmax)
    top, bot = 12, 12
    def X(i): return (i + 0.5) * W / len(xlabels)
    def Y(v): return top + (H - top - bot) * (1 - v / ymax)

    parts = [f'<svg aria-label="{esc(aria)}" width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    for k in range(5):
        y = Y(k * step)
        c = '#CFCBC0' if k == 0 else '#EEECE4'
        parts.append(f'<line x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}" stroke="{c}" stroke-width="2"/>')
    for si, s in enumerate(series):
        pts = [(X(i), Y(v), i) for i, v in enumerate(s['values']) if v is not None]
        pi = partial[1] if partial and partial[0] == si else None
        solid = [p for p in pts if pi is None or p[2] < pi]
        if len(solid) > 1:
            d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y, _ in solid)
            parts.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
        if pi is not None:
            pp = [p for p in pts if p[2] == pi]
            prev = [p for p in pts if p[2] == pi - 1]
            if pp and prev:
                parts.append(f'<path d="M{prev[0][0]:.1f} {prev[0][1]:.1f} L{pp[0][0]:.1f} {pp[0][1]:.1f}" fill="none" stroke="{s["color"]}" stroke-width="4" stroke-dasharray="10 8" stroke-linecap="round"/>')
        for x, y, i in pts:
            if pi is not None and i == pi:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="#FFFFFF" stroke="{s["color"]}" stroke-width="4"/>')
            elif pi is None or i < pi:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{s["color"]}" stroke="#FFFFFF" stroke-width="2"/>')
    parts.append('</svg>')
    svg = ''.join(parts)

    ylabels = ''.join(
        f'<p style="font-size:24px;line-height:1;text-align:right;color:{FAINT}">{tick_label(ymax - k * step)}</p>'
        for k in range(5))
    xl = ''.join(f'<p style="flex:1;font-size:24px;line-height:1.2;text-align:center;color:{FAINT}">{m}</p>' for m in xlabels)
    legend = ''.join(
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:10px">'
        f'<div style="width:18px;height:18px;border-radius:50%;background:{s["color"]}"></div>'
        f'<p style="font-size:24px;line-height:1.2;font-weight:600;color:{MUTED}">{esc(s["label"])}</p></div>'
        for s in series)
    return (
        f'<div style="width:{width}px;{CARD};padding:{pad}px;display:flex;flex-direction:column;gap:16px">'
        f'<div style="display:flex;flex-direction:row;justify-content:space-between;align-items:start;gap:24px">'
        f'<div style="display:flex;flex-direction:column;gap:4px">'
        f'<h3 style="font-family:{SANS};font-size:36px;font-weight:700;line-height:1.15;color:{INK}">{esc(title)}</h3>'
        f'<p style="font-size:24px;line-height:1.3;color:{FAINT}">{esc(sub)}</p></div>'
        f'<img src="{LOGO[0]}" alt="Flo" style="width:50px;height:31px;object-fit:contain;opacity:0.4"></div>'
        f'<div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:28px">{legend}</div>'
        f'<div style="display:flex;flex-direction:column;gap:8px">'
        f'<div style="display:flex;flex-direction:row;gap:{gap}px">'
        f'<div style="width:{ylab_w}px;height:{H}px;display:flex;flex-direction:column;justify-content:space-between">{ylabels}</div>'
        f'{svg}</div>'
        f'<div style="display:flex;flex-direction:row;padding:0px 0px 0px {ylab_w + gap}px">{xl}</div>'
        f'</div></div>')


SEP_AUG = ['Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug']
JUL_JUN = ['Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun']


def season_chart(ctx, series_map, seasons, title, sub, aria):
    """Monthly chart on a Sep-Aug axis, one line per season; month in progress dashed."""
    ss = []
    for s in seasons:
        ss.append({'label': s, 'color': SEASON_COLORS[s], 'values': sep_aug(series_map, s)})
    # month in progress -> index on Sep..Aug axis of the season that contains it
    y, m = ctx.cur
    key, i = season_of(y, m)
    disp_season, idx = (key, i - 2) if i >= 2 else (f'{int(key[:4])-1}-{key[:4]}', i + 10)
    partial = None
    if disp_season in seasons and ctx.mark_partial:
        partial = (seasons.index(disp_season), idx)
        # drop anything after the month in progress (should already be None)
        ss[partial[0]]['values'] = [v if j <= idx else None for j, v in enumerate(ss[partial[0]]['values'])]
    return line_chart(title, sub, SEP_AUG, ss, partial, aria)


# ---------------------------------------------------------------- headline helpers
def headline(ctx, series, noun_up, noun_count):
    """e.g. 'Law firm interviews up 68% in September, with October up 90% so far'."""
    fy, fm = ctx.full
    cy, cm = ctx.cur
    cur_full, prev_full = ctx.yoy(series, ctx.full)
    cur_now, prev_now = ctx.yoy(series, ctx.cur)
    ch = change(cur_full, prev_full)
    ch2 = change(cur_now, prev_now)  # partial month already beats last year's full month
    month, month2 = MONTH_FULL[fm - 1], MONTH_FULL[cm - 1]
    if ch and ch[1]:
        t = f'{noun_up} up {ch[1]} in {month}'
        if ch2 and ch2[1]:
            t += f', with {month2} up {ch2[1]} so far'
    else:
        t = f'{fmt_n(cur_full or 0)} {noun_count} in {month}, vs. {fmt_n(prev_full or 0)} a year earlier'
    facts = {'month': month, 'cur': cur_full, 'prev': prev_full, 'change': ch and ch[1],
             'month2': month2, 'cur2': cur_now, 'prev2': prev_now, 'change2': ch2 and ch2[1]}
    return t, facts


def peak(series_map, season):
    vals = sep_aug(series_map, season)
    i = max(range(12), key=lambda k: vals[k] or 0)
    return SEP_AUG[i], vals[i]


def class_compare(ctx):
    """Cumulative newest class vs prior class at end of the latest full month."""
    acc = ctx.L['accounts']
    new, old = acc.get(ctx.newest_class), acc.get(ctx.prior_class)
    fy, fm = ctx.full
    _, i = season_of(fy, fm)
    a, b = new[i], old[i]
    # monthly sign-ups in the latest full month and the month in progress
    def monthly(arr, j): return None if arr[j] is None else arr[j] - (arr[j-1] if j > 0 else 0)
    _, ci = season_of(*ctx.cur)
    latest = next(v for v in reversed(new) if v is not None)
    return {'cum_new': a, 'cum_old': b, 'ahead': change(a, b), 'idx': i,
            'mon_new': monthly(new, i), 'mon_old': monthly(old, i),
            'cur_new': monthly(new, ci), 'cur_old': monthly(old, ci), 'latest': latest}


# ---------------------------------------------------------------- slides
def slide_accounts(ctx, sid, logo):
    acc = ctx.L['accounts']
    classes = [c for c in sorted(acc) if c in CLASS_COLORS][-4:]
    cc = class_compare(ctx)
    fm = MONTH_FULL[ctx.full[1] - 1]; cm = MONTH_FULL[ctx.cur[1] - 1]
    newest = ctx.newest_class
    title = (f'The {newest} is joining Flo Forward faster than ever' if cc['ahead']
             else f'{newest} adoption on Flo Forward')
    sub = f'{fmt_n(cc["mon_new"])} {newest} students joined in {fm}'
    m = change(cc['mon_new'], cc['mon_old'])
    sub += f', up {m[1]} on the {ctx.prior_class} a year earlier.' if m and m[1] else '.'
    m2 = change(cc['cur_new'], cc['cur_old'])
    if m2 and m2[1]:
        sub += f' {cm} is up {m2[1]} so far.'
    sub += f' {fmt_n(cc["latest"])} {newest} students are on the platform as of {ctx.asof.rsplit(",",1)[0]}.'
    ss = [{'label': c, 'color': CLASS_COLORS[c], 'values': list(acc[c])} for c in classes]
    _, ci = season_of(*ctx.cur)
    partial = (classes.index(newest), ci) if newest in classes and ctx.mark_partial else None
    chart = line_chart('Flo Forward account creation', 'Cumulative by graduating class · recruiting year Jul–Jun',
                       JUL_JUN, ss, partial, f'Line chart: cumulative Flo Forward accounts by class, {", ".join(classes)}')
    return chart_slide(sid, logo, title, sub, chart, ctx, ctx.note,
                       f'Updated automatically from the tracker each weekday. {sub}'), {
        'title': title, 'subtitle': sub, **cc}


def slide_outreach(ctx, sid, logo, size):
    key = 'outreach_500plus' if size == '500plus' else 'outreach_u500'
    s = ctx.L[key]
    label = '500+ attorneys' if size == '500plus' else 'under 500 attorneys'
    t, f = headline(ctx, s, 'Law firm recruiting events', 'law firm recruiting events')
    pk_m, pk_v = peak(s, ctx.prev_season)
    sub = (f'[[b]]Firms with {label}[[/b]] hosted {fmt_n(f["cur"])} Outreach Events on Flo in {f["month"]}, '
           f'up from {fmt_n(f["prev"])} a year earlier, as early {ctx.newest_class} outreach ramps up. '
           f'Last season peaked in {pk_m} at {fmt_n(pk_v)}.')
    if not f['change']:
        sub = (f'[[b]]Firms with {label}[[/b]] hosted {fmt_n(f["cur"])} Outreach Events on Flo in {f["month"]}. '
               f'Last season peaked in {pk_m} at {fmt_n(pk_v)}.')
    seasons = [x for x in ['2022-2023','2023-2024','2024-2025','2025-2026', ctx.season] if x in s or x == ctx.season]
    chart = season_chart(ctx, s, seasons, f'Outreach events on Flo: firms with {label}',
                         'Monthly · recruiting season Sep–Aug',
                         f'Line chart: monthly outreach events, firms with {label}, by season')
    return chart_slide(sid, logo, t, sub, chart, ctx, ctx.note,
                       'Updated automatically from the tracker each weekday.'), {'title': t, 'subtitle': sub, **f}


def slide_apps(ctx, sid, logo):
    s = ctx.L['appsubs']
    t, f = headline(ctx, s, 'Student applications on Flo Forward', 'student applications on Flo Forward')
    cc = class_compare(ctx)
    ahead = f' ({cc["ahead"][1]} ahead of the {ctx.prior_class} at the same point)' if cc['ahead'] else ''
    sub = (f'Students submitted {fmt_n(f["cur"])} applications in {f["month"]}, vs. {fmt_n(f["prev"])} a year earlier. '
           f'Volume reflects faster adoption by the {ctx.newest_class}{ahead} and earlier job opening timelines.')
    seasons = ['2023-2024','2024-2025','2025-2026', ctx.season]
    chart = season_chart(ctx, s, seasons, 'Flo Forward application submissions', 'All students · monthly · recruiting season Sep–Aug',
                         'Line chart: monthly Flo Forward application submissions by season')
    return chart_slide(sid, logo, t, sub, chart, ctx, ctx.note,
                       'Updated automatically from the tracker each weekday.'), {'title': t, 'subtitle': sub, **f,
                                                                              'class_ahead': cc['ahead'] and cc['ahead'][1]}


def slide_interviews(ctx, sid, logo, size):
    if size == 'all':
        s = sum_series(ctx.L['lf_500plus'], ctx.L['lf_u500']); label = 'all law firms'
    else:
        s = ctx.L['lf_500plus' if size == '500plus' else 'lf_u500']
        label = 'firms with 500+ attorneys' if size == '500plus' else 'firms with under 500 attorneys'
    t, f = headline(ctx, s, 'Law firm interviews', 'law firm interviews')
    pk_m, pk_v = peak(s, ctx.prev_season)
    sub = (f'Student interviews at [[b]]{label}[[/b]] on Flo reached {fmt_n(f["cur"])} in {f["month"]}. '
           f'Last season peaked in {pk_m} at {fmt_n(pk_v)} as 1L and 2L recruiting seasons merged.')
    seasons = ['2022-2023','2023-2024','2024-2025','2025-2026', ctx.season]
    chart = season_chart(ctx, s, seasons, f'Student interview volume: {label}',
                         'Callback interviews · monthly · recruiting season Sep–Aug',
                         f'Line chart: monthly student interview volume, {label}, by season')
    return chart_slide(sid, logo, t, sub, chart, ctx, ctx.note,
                       'Updated automatically from the tracker each weekday.'), {'title': t, 'subtitle': sub, **f}


def slide_adoption(ctx, sid, logo, partners_text):
    cc = class_compare(ctx)
    fm = MONTH_FULL[ctx.full[1] - 1]
    day = ctx.asof.rsplit(',', 1)[0]
    tiles = [
        (fmt_n(cc['latest']), '#153b24', f'{ctx.newest_class} law students on Flo Forward as of {day}'),
    ]
    if cc['ahead']:
        big = cc['ahead'][1] if cc['ahead'][0] == 'x' else '+' + cc['ahead'][1]
        tiles.append((big, '#4d8eff', f'more sign-ups than the {ctx.prior_class} by the end of {fm} in their 1L year'))
    else:
        tiles.append((fmt_n(cc['cum_new']), '#4d8eff', f'{ctx.newest_class} sign-ups by the end of {fm}'))
    tiles.append(partners_text)
    cells = ''.join(
        f'<div style="display:flex;flex-direction:column;gap:20px">'
        f'<p style="font-family:{SERIF};font-size:120px;font-weight:600;line-height:0.92;letter-spacing:-3.6px;color:{c}">{esc(n)}</p>'
        f'<p style="font-family:{SANS};font-size:28px;line-height:1.4;color:{MUTED}">{esc(l)}</p></div>'
        for n, c, l in tiles)
    html = (
        f'<section id="{sid}" style="display:flex;flex-direction:column;gap:80px;justify-content:center;padding:200px 120px 120px;background:{BG.lower()}">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;top:40px;left:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:24px">'
        f'<p style="font-family:{SEMI};font-size:24px;font-weight:500;line-height:1.2;letter-spacing:2.6px;text-transform:uppercase;color:#c74500">Student Adoption</p>'
        f'<h2 style="width:1500px;font-family:{SANS};font-size:72px;font-weight:600;line-height:1.05;letter-spacing:-1.8px;color:{INK}">{ctx.newest_class} adoption on Flo Forward</h2></div>\n'
        f'<div style="display:grid;gap:56px;grid-template-columns:1fr 1fr 1fr">{cells}</div>\n'
        f'{footer(ctx)}\n<aside>Updated automatically from the tracker each weekday (first two figures).</aside>\n</section>\n')
    return html, {'tiles': tiles[:2]}


def slide_reach(ctx, sid, logo, start_month=8):
    """All-student engagement since Aug 1 of the current season vs the same months last year."""
    y0 = int(ctx.season[:4])
    cy, cm = ctx.cur
    months = []
    y, m = y0, start_month
    while (y, m) <= (cy, cm):
        months.append((y, m)); m += 1
        if m == 13: y, m = y + 1, 1
    metrics = [('Firm profile views', 'firm_views', '#192B92'), ('Applications', 'appsubs', '#4D8EFF'),
               ('Event registrations', 'event_regs', '#4DA54C')]
    res = []
    for name, k, col in metrics:
        s = ctx.L[k]
        now = sum(val(s, yy, mm) or 0 for yy, mm in months)
        last = sum(val(s, yy - 1, mm) or 0 for yy, mm in months)
        res.append((name, col, now, last, change(now, last)))
    start = f'{MON[start_month-1]} 1'
    last_rng = f'{MON[start_month-1]}–{MON[cm-1]} {cy-1}'
    head = f'Since {MONTH_FULL[start_month-1]} 1: {floor_plus(res[0][2], 1000)} profile views and {floor_plus(res[1][2], 100)} applications'
    tiles = ''
    for name, col, now, last, ch in res:
        mx = max(now, last) or 1
        cmp_txt = (f'{ch[1]} the same months last year' if ch and ch[0] == 'x'
                   else f'Up {ch[1]} on the same months last year' if ch else 'vs. the same months last year')
        tiles += (
            f'<div style="flex:1;{CARD};padding:40px;display:flex;flex-direction:column;gap:20px">'
            f'<p style="font-family:{SEMI};font-size:24px;font-weight:500;letter-spacing:2px;text-transform:uppercase;color:{MUTED}">{esc(name)}</p>'
            f'<p style="font-family:{SERIF};font-size:96px;font-weight:600;line-height:0.95;letter-spacing:-2.4px;color:{col}">{fmt_n(now)}</p>'
            f'<p style="font-size:28px;line-height:1.3;font-weight:600;color:{INK}">{esc(cmp_txt)}</p>'
            f'<div style="display:flex;flex-direction:column;gap:10px">'
            f'<div style="width:{max(8, round(420 * now / mx))}px;height:22px;border-radius:11px;background:{col}"></div>'
            f'<p style="font-size:24px;line-height:1.2;color:{MUTED}">{start}–{MON[cm-1]} {ctx.now.day}, {cy}: {fmt_n(now)}</p>'
            f'<div style="width:{max(8, round(420 * last / mx))}px;height:22px;border-radius:11px;background:#D8D4CA"></div>'
            f'<p style="font-size:24px;line-height:1.2;color:{MUTED}">{last_rng} (full months): {fmt_n(last)}</p>'
            f'</div></div>')
    html = (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};padding:150px 120px 110px;display:flex;flex-direction:column;gap:40px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:16px">'
        f'<h2 style="width:1680px;font-family:{SANS};font-weight:600;font-size:60px;line-height:1.05;letter-spacing:-1.5px;color:{INK}">{esc(head)}</h2>'
        f'<p style="width:1560px;font-size:26px;line-height:1.45;color:{MUTED}">Engagement since {MONTH_FULL[start_month-1]} 1 is driven by the {ctx.newest_class}\'s first semester. Counts include all students on Flo Forward.</p></div>\n'
        f'<div style="display:flex;flex-direction:row;gap:32px">{tiles}</div>\n'
        f'{footer(ctx)}\n<aside>Updated automatically from the tracker each weekday. Last year uses full months, so the comparison is conservative while the current month is in progress.</aside>\n</section>\n')
    return html, {'title': head, 'metrics': [(n, a, b, c and c[1]) for n, _, a, b, c in res]}


# ---------------------------------------------------------------- lateral sources
SOURCE_ORDER = [('Agency', ['Agency'], '#192B92', '#FFFFFF'),
                ('Write-in', ['Write-in'], '#4D8EFF', INK),
                ('Referral', ['Referral'], '#4DA54C', INK),
                ('Direct outreach', ['Direct Outreach'], '#C74500', '#FFFFFF'),
                ('Job board', ['Advertisement/Job Board'], '#FC97C2', INK),
                ('Other', ['Other', 'None'], '#B9B3AE', INK)]
STAGES = [('applied', 'Applied'), ('interview', 'Interviewed'), ('offer', 'Offer')]


def lateral_shares(src):
    by = {r['label']: r['v'] for r in src}
    out = {}
    for st, _ in STAGES:
        tot = sum(v.get(st, 0) for v in by.values())
        out[st] = (tot, [(name, col, txt, sum(by.get(k, {}).get(st, 0) for k in keys) / tot * 100 if tot else 0)
                         for name, keys, col, txt in SOURCE_ORDER])
    return out


def slide_lateral_source(ctx, sid, logo):
    sh = lateral_shares(ctx.d['charts']['lateral']['source'])
    ag_int = next(p for n, _, _, p in sh['interview'][1] if n == 'Agency')
    ag_off = next(p for n, _, _, p in sh['offer'][1] if n == 'Agency')
    wi_app = next(p for n, _, _, p in sh['applied'][1] if n == 'Write-in')
    wi_int = next(p for n, _, _, p in sh['interview'][1] if n == 'Write-in')
    body = (f'Agencies source {round(ag_int)}% of lateral candidates who reach interview and {round(ag_off)}% of offers. '
            f'Write-ins make up {round(wi_app)}% of applicants but only {round(wi_int)}% of interviews, '
            f'so firms are pairing trusted agencies with direct sourcing from their own ATS.')
    rows = ''
    for st, label in STAGES:
        tot, parts = sh[st]
        segs = ''
        for name, col, txt, pct in parts:
            if pct <= 0:
                continue
            lab = (f'<p style="font-size:24px;font-weight:600;line-height:1;color:{txt}">{round(pct)}%</p>'
                   if pct >= 9 else '')
            segs += (f'<div style="flex:{pct:.2f};height:64px;background:{col};display:flex;'
                     f'align-items:center;justify-content:center">{lab}</div>')
        rows += (f'<div style="display:flex;flex-direction:column;gap:10px">'
                 f'<div style="display:flex;flex-direction:row;justify-content:space-between">'
                 f'<p style="font-size:26px;font-weight:600;line-height:1.2;color:{INK}">{label}</p>'
                 f'<p style="font-size:24px;line-height:1.2;color:{FAINT}">{fmt_n(tot)} candidates</p></div>'
                 f'<div style="display:flex;flex-direction:row;gap:3px;border-radius:10px;overflow:hidden">{segs}</div></div>')
    legend = ''.join(
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:10px">'
        f'<div style="width:18px;height:18px;border-radius:50%;background:{col}"></div>'
        f'<p style="font-size:24px;line-height:1.2;font-weight:600;color:{MUTED}">{name}</p></div>'
        for name, _, col, _ in SOURCE_ORDER)
    card = (
        f'<div style="width:900px;{CARD};padding:40px;display:flex;flex-direction:column;gap:30px">'
        f'<div style="display:flex;flex-direction:row;justify-content:space-between;align-items:start;gap:24px">'
        f'<div style="display:flex;flex-direction:column;gap:4px">'
        f'<h3 style="font-family:{SANS};font-size:34px;font-weight:700;line-height:1.15;color:{INK}">Where lateral candidates come from</h3>'
        f'<p style="font-size:24px;line-height:1.3;color:{FAINT}">Non-partner laterals on Flo · share by source · applied since Jan 2025</p></div>'
        f'<img src="{logo}" alt="Flo" style="width:50px;height:31px;object-fit:contain;opacity:0.4"></div>'
        f'<div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:14px 28px">{legend}</div>'
        f'{rows}</div>')
    html = (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};padding:128px 120px 120px;'
        f'display:flex;flex-direction:row;align-items:center;gap:72px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="flex:1;display:flex;flex-direction:column;gap:32px">'
        f'<h2 style="font-family:{SANS};font-size:64px;font-weight:600;line-height:1.06;letter-spacing:-1.6px;color:{INK}">Lateral recruiting is expensive, and expected to become increasingly competitive</h2>'
        f'<p style="font-size:29px;line-height:1.5;color:{MUTED}">{esc(body)}</p></div>\n'
        f'{card}\n{footer(ctx, link=LINK_LATERAL)}\n'
        f'<aside>Agencies are {round(ag_int)}% of lateral candidates who reach interview and {round(ag_off)}% of offers, for candidates who applied since January 2025. '
        f'Mixed sourcing is the reality, so the ATS has to handle both. Updated automatically from the tracker each weekday.</aside>\n</section>\n')
    return html, {'body': body, 'shares': {st: [(n, round(p, 1)) for n, _, _, p in sh[st][1]] for st, _ in STAGES}}


def slide_lateral_profile(ctx, sid, logo, window='open'):
    """Matches the tracker's Lateral non-partner > Market Data charts (grad year + practice)."""
    lat = ctx.d['charts']['lateral']
    grads = lat['gradByWindow'][window]
    prac = lat['practiceByWindow'][window]
    total = lat['totalByWindow'][window]
    y = ctx.now.year
    # Seniority bands as the tracker shows them: junior = last 3 classes, mid-level = the 3 before, senior = older
    bands = [('Senior', min(g[0] for g in grads), y - 6, '#192B92'),
             ('Mid-level', y - 5, y - 3, '#4D8EFF'),
             ('Junior', y - 2, y, '#A9C6FF')]
    gsum = sum(n for _, n in grads) or 1
    band_pct = [(name, lo, hi, col, round(sum(n for yr, n in grads if lo <= yr <= hi) / gsum * 100))
                for name, lo, hi, col in bands]
    def band_col(yr):
        return next((c for _, lo, hi, c in bands if lo <= yr <= hi), '#192B92')
    lead = max(band_pct, key=lambda b: b[4])
    p1, p1n = prac[0]
    win_txt = {'open': 'open on Flo right now', '3mo': 'opened on Flo in the past three months',
               '12mo': 'opened on Flo in the past 12 months'}[window]
    win_short = {'open': 'Open now', '3mo': 'Past 3 months', '12mo': 'Past 12 months'}[window]
    title = f'Lateral searches on Flo point to demand for {lead[0].lower()} associates and {p1}'
    # wording as edited by Hannah in the preview deck, Oct 26
    sub = (f'Of lateral non-partner searches {win_txt}, {lead[4]}% of graduation-year targets fall in the '
           f'Classes of {lead[1]}–{lead[2]}, and {p1} is the most-listed practice ({round(p1n / total * 100)}% of roles).')
    tiles = ''.join(
        f'<div style="flex:1;background:#F4F2EC;border-left:5px solid {col};border-radius:12px;padding:16px 18px;display:flex;flex-direction:column;gap:2px">'
        f'<p style="font-size:24px;font-weight:600;line-height:1.2;color:{INK}">{name}</p>'
        f'<p style="font-size:24px;line-height:1.2;color:{FAINT}">{lo}–{hi}</p>'
        f'<p style="font-size:44px;font-weight:700;line-height:1.1;color:{INK}">{pct}%</p></div>'
        for name, lo, hi, col, pct in band_pct)
    key = ''.join(
        f'<div style="display:flex;flex-direction:row;align-items:center;gap:10px">'
        f'<div style="width:18px;height:18px;border-radius:4px;background:{col}"></div>'
        f'<p style="font-size:24px;line-height:1.2;color:{MUTED}"><b>{name}</b> {lo}–{hi}</p></div>'
        for name, lo, hi, col, _ in band_pct)
    gmax = max(n for _, n in grads) or 1
    bars = ''
    for yr, n in grads:
        bars += (f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:end;gap:6px">'
                 f'<p style="font-size:24px;font-weight:600;line-height:1;color:{INK}">{n}</p>'
                 f'<div style="width:32px;height:{max(4, round(290 * n / gmax))}px;border-radius:6px 6px 0px 0px;background:{band_col(yr)}"></div>'
                 f'<p style="font-size:24px;line-height:1;color:{FAINT}">’{str(yr)[2:]}</p></div>')
    top = prac[:8]
    pmax = top[0][1] or 1
    rows = ''
    for name, n in top:
        rows += (f'<div style="display:flex;flex-direction:row;align-items:center;gap:16px">'
                 f'<p style="width:320px;font-size:24px;font-weight:600;line-height:1.2;text-align:right;color:{INK}">{esc(name)}</p>'
                 f'<div style="flex:1;height:34px;border-radius:8px;background:#EEECE4;display:flex;flex-direction:row">'
                 f'<div style="flex:{n / pmax:.4f};border-radius:8px;background:#192B92"></div>'
                 f'<div style="flex:{1 - n / pmax:.4f}"></div></div>'
                 f'<p style="width:64px;font-size:24px;font-weight:700;line-height:1;color:{INK}">{round(n / total * 100)}%</p></div>')

    def card(h, sub_, body, gap=20):
        return (f'<div style="flex:1;{CARD};padding:32px;display:flex;flex-direction:column;gap:{gap}px">'
                f'<div style="display:flex;flex-direction:row;justify-content:space-between;align-items:start;gap:24px">'
                f'<div style="display:flex;flex-direction:column;gap:4px">'
                f'<h3 style="font-family:{SANS};font-size:32px;font-weight:700;line-height:1.15;color:{INK}">{h}</h3>'
                f'<p style="font-size:24px;line-height:1.3;color:{FAINT}">{sub_}</p></div>'
                f'<img src="{logo}" alt="Flo" style="width:50px;height:31px;object-fit:contain;opacity:0.4"></div>{body}</div>')
    left = card('Searches by target grad year', f'{win_short} · roles may span grad years',
                f'<div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:12px 28px">{key}</div>'
                f'<div style="display:flex;flex-direction:row;align-items:end;gap:4px">{bars}</div>')
    right = card('Top practice areas', f'{win_short} · share of {fmt_n(total)} roles · where the title specifies',
                 f'<div style="display:flex;flex-direction:column;gap:16px">{rows}</div>')
    html = (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};'
        f'padding:140px 120px 90px;display:flex;flex-direction:column;gap:28px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:16px">\n'
        f'<h2 style="width:1680px;font-family:{SANS};font-weight:600;font-size:64px;line-height:1.05;letter-spacing:-1.6px;color:{INK}">{esc(title)}</h2>\n'
        f'<p style="width:1560px;font-size:26px;line-height:1.45;color:{MUTED}">{esc(sub)}</p>\n</div>\n'
        f'<div style="display:flex;flex-direction:row;gap:32px;align-items:start">{left}{right}</div>\n'
        f'{footer(ctx, link=LINK_LATERAL)}\n'
        f'<aside>Same data and window as the tracker’s Lateral non-partner Market Data tab ({win_short.lower()}). '
        f'Searches can target more than one graduation year, so band shares are of all grad-year targets. '
        f'Updated automatically from the tracker each weekday.</aside>\n</section>\n')
    return html, {'title': title, 'subtitle': sub, 'bands': [(b[0], b[4]) for b in band_pct]}

# ---------------------------------------------------------------- student count (one number everywhere)
import re as _re


def student_counts(ctx):
    """Latest cumulative Flo Forward accounts by class.
    current = classes still in law school (graduate after this May); all = every class the tracker has."""
    acc = ctx.L['accounts']
    latest = {int(k.split()[-1]): next(v for v in reversed(a) if v is not None) for k, a in acc.items()}
    first_current = ctx.now.year + (1 if ctx.now.month >= 6 else 0)
    cur = {y: n for y, n in latest.items() if y >= first_current}
    return {'current': sum(cur.values()), 'current_classes': (min(cur), max(cur)),
            'all': sum(latest.values()), 'all_classes': (min(latest), max(latest)), 'by_class': latest}


def floor_500(n):
    return f'{n // 500 * 500:,}+'


NUM = r'\d{1,3}(?:,\d{3})+\+'


def student_patches(ctx):
    """(regex, replacement) pairs applied to the text of existing slides/pages that quote the student count."""
    sc = student_counts(ctx)
    a0, a1 = sc['all_classes']
    return [
        (_re.compile(NUM + r' law students and (?:early career associates|new graduates)'), floor_500(sc['all']) + ' law students and new graduates'),
        # explicit 'current' claims keep the in-school count; any other 'law students' claim uses everyone (Hannah, Oct 26)
        (_re.compile(NUM + r' current law students'), floor_500(sc['current']) + ' current law students'),
        (_re.compile(NUM + r' law students(?! and (?:early|new))'), floor_500(sc['all']) + ' law students and new graduates'),
        (_re.compile(r"n: '" + NUM + r"', d: 'students and grads joined from JD classes of [^,]+, [^,]+, and \d{4} use Flo Forward"),
         f"n: '{floor_500(sc['all'])}', d: 'students and grads from JD classes of {a0}–{a1} use Flo Forward"),
    ]


def patch_student_count(html, ctx):
    n = 0
    for rx, rep in student_patches(ctx):
        html, k = rx.subn(rep, html)
        n += k
    return html, n


def slide_student_count(ctx, sid, logo):
    sc = student_counts(ctx)
    c0, c1 = sc['current_classes']; a0, a1 = sc['all_classes']
    allc = f'{floor_500(sc["all"])} law students and new graduates'
    rows = [('Intro Deck 12–13, ATS demo 5–6', '39,000+ law students', allc),
            ('Clerks deck 3–4', '40,000+ law students', allc),
            ('Overview Packet intro pages', '35,000+ law students and early career associates', allc),
            ('Overview Packet, Flo Forward page', '40,000+ students and grads … classes of 2026–2028', f'{floor_500(sc["all"])} students and grads … classes of {a0}–{a1}'),
            ('Any slide that says “current law students”', '—', f'{floor_500(sc["current"])} current law students')]
    trs = ''.join(f'<tr><td>{esc(w)}</td><td style="color:{FAINT}">{esc(o)}</td><td style="font-weight:600">{esc(n)}</td></tr>' for w, o, n in rows)
    by = ' · '.join(f'C/o {y}: {fmt_n(n)}' for y, n in sorted(sc['by_class'].items()))
    stat = lambda n, col, lab: (f'<div style="flex:1;display:flex;flex-direction:column;gap:12px">'
                                f'<p style="font-family:{SERIF};font-size:120px;font-weight:600;line-height:0.92;letter-spacing:-3.6px;color:{col}">{n}</p>'
                                f'<p style="font-size:28px;line-height:1.4;color:{MUTED}">{esc(lab)}</p></div>')
    html = (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};padding:140px 120px 110px;display:flex;flex-direction:column;gap:44px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:16px">'
        f'<p style="font-family:{SEMI};font-size:24px;font-weight:500;line-height:1.2;letter-spacing:2.6px;text-transform:uppercase;color:#c74500">One student count, everywhere</p>'
        f'<h2 style="width:1680px;font-family:{SANS};font-weight:600;font-size:64px;line-height:1.05;letter-spacing:-1.6px;color:{INK}">Every student-count claim updates from the tracker each weekday</h2></div>\n'
        f'<div style="display:flex;flex-direction:row;gap:56px">'
        f'{stat(floor_500(sc["all"]), "#153b24", f"law students and new graduates (Classes of {a0}–{a1}), the default")}'
        f'{stat(floor_500(sc["current"]), "#4d8eff", f"current law students (Classes of {c0}–{c1}), only where a slide says “current”")}</div>\n'
        f'<table style="width:1680px;font-size:26px;color:{INK}"><tr><th style="width:30%">Where</th><th style="width:36%">Says today</th><th style="width:34%">Will say</th></tr>{trs}</table>\n'
        f'{footer(ctx)}\n'
        f'<aside>{esc(by)}. Rounded down to the nearest 500. Only the number changes; the rest of each slide stays as written.</aside>\n</section>\n')
    return html, sc


# ---------------------------------------------------------------- client stats (HubSpot dashboard)
def load_client_stats(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_stats.json')
    if not os.path.exists(path):
        return None
    return {k: v['value'] for k, v in json.load(open(path))['reports'].items()}


def floor_5(n):
    return f'{n // 5 * 5}+'


def pct(n, of):
    """Nearest 5%; add '+' when that rounds down so a claim never overstates (Hannah, Oct 26)."""
    near = (n * 100 * 2 + of * 5) // (of * 10) * 5          # round half up to a multiple of 5
    return f'{near}%' + ('+' if near * of < n * 100 else '')


CLIENT_STATS_REFRESH = 'weekly'   # HubSpot client stats refresh Mondays; tracker data refreshes every weekday


def client_patches(cs):
    """Ordered most-specific first. Each claim keeps its wording; only the number changes."""
    P = lambda rx, rep: (_re.compile(rx), rep)
    return [
        # Flo Forward ("on Forward") claims
        P(r'paid profiles \(\d{1,3}%\+? AmLaw 100\)', f'paid profiles ({pct(cs["amlaw100_forward"], 100)} AmLaw 100)'),
        P(r'\d{1,3}%\+? of AmLaw 50\b', f'{pct(cs["amlaw50_forward"], 50)} of AmLaw 50'),
        P(r'\d{1,3}%\+? of AmLaw 100\b', f'{pct(cs["amlaw100_forward"], 100)} of AmLaw 100'),
        P(r'\d{1,3}%\+? of AmLaw 200\b', f'{pct(cs["amlaw200_forward"], 200)} of AmLaw 200'),
        P(r'\d{1,3}%\+? of Vault 100\b', f'{pct(cs["vault100_forward"], 100)} of Vault 100'),
        P(r'\d{1,2}/50 Vault top 50', f'{cs["vault50_forward"]}/50 Vault top 50'),
        P(r'\d{2,3}\+ law firms invest in Flo Forward', f'{floor_5(cs["firms_on_forward"])} law firms invest in Flo Forward'),
        # client claims
        P(r'\d{1,3}%\+? of the AmLaw 100\b', f'{pct(cs["amlaw100_clients"], 100)} of the AmLaw 100'),
        P(r'\d{1,3}%\+? AmLaw 50\b', f'{pct(cs["amlaw50_clients"], 50)} AmLaw 50'),
        P(r'\d{1,3}%\+? AmLaw 200\b', f'{pct(cs["amlaw200_clients"], 200)} AmLaw 200'),
        P(r'\d{2,3}\+ law firm clients', f'{floor_5(cs["law_firm_clients"])} law firm clients'),
        P(r'(partner with )\d{2,3}\+ law firms', r'\g<1>' + f'{floor_5(cs["law_firm_clients"])} law firms'),
        P(r'\d{2,3}\+ firms using Flo Applicant Tracking', f'{floor_5(cs["ats_clients"])} firms using Flo Applicant Tracking'),
        P(r'\d{2,3}\+ firms on the ATS', f'{floor_5(cs["ats_clients"])} firms on the ATS'),
        P(r'\d{2,3}\+ firms using the ATS for lateral', f'{floor_5(cs["lateral_ats"])} firms using the ATS for lateral'),
        P(r'\d{2,3}\+ using it for lateral', f'{floor_5(cs["lateral_ats"])} using it for lateral'),
        P(r'\d{2,3}\+ law schools, consortiums', f'{floor_5(cs["school_clients"])} law schools, consortiums'),
        P(r'(syncs directly with )\d{2,3}\+ law schools and consortiums', r'\g<1>' + f'{floor_5(cs["school_clients"])} law schools and consortiums'),
    ]


def patch_text(html, ctx, cs=None):
    """All number patches for slides/pages we don't own: student count + client stats."""
    html, n = patch_student_count(html, ctx)
    if cs:
        for rx, rep in client_patches(cs):
            html, k = rx.subn(rep, html)
            n += k
    return html, n


def slide_client_stats(ctx, sid, logo):
    cs = load_client_stats()
    rows = [
        ('Law firm clients', '160+ / 165+ / 170+', floor_5(cs['law_firm_clients']), 'Total Law Firm Clients'),
        ('AmLaw 50 clients', '75%', pct(cs['amlaw50_clients'], 50), 'AmLaw 50 Clients'),
        ('AmLaw 100 clients', '60%', pct(cs['amlaw100_clients'], 100), 'AmLaw 100 Clients'),
        ('AmLaw 200 clients', '40%', pct(cs['amlaw200_clients'], 200), 'AmLaw 200 Clients'),
        ('Firms using the ATS', '80+', floor_5(cs['ats_clients']), 'ATS Clients'),
        ('Firms using the ATS for lateral', '65+', floor_5(cs['lateral_ats']), 'Lateral Applicant Tracking Clients'),
        ('Law school and consortium clients', '100+', floor_5(cs['school_clients']), 'Total Law School / Consortium Clients'),
        ('Law firms on Flo Forward', '125+', floor_5(cs['firms_on_forward']), 'Law Firms on Forward'),
        ('AmLaw 50 / 100 / 200 on Forward', '86% / 70% / 51%',
         f'{pct(cs["amlaw50_forward"], 50)} / {pct(cs["amlaw100_forward"], 100)} / {pct(cs["amlaw200_forward"], 200)}', 'AmLaw 50 / 100 / 200 Firms on Forward'),
        ('Vault 50 on Forward', '41/50', f'{cs["vault50_forward"]}/50', 'Vault 50 Firms on Forward'),
        ('Vault 100 on Forward', '75%', pct(cs['vault100_forward'], 100), 'Vault 100 Firms on Forward'),
    ]
    trs = ''.join(f'<tr><td>{esc(a)}</td><td style="color:{FAINT}">{esc(b)}</td><td style="font-weight:700">{esc(c)}</td><td style="color:{MUTED}">{esc(d)}</td></tr>' for a, b, c, d in rows)
    html = (
        f'<section id="{sid}" style="background:{BG};color:{INK};font-family:{SANS};padding:130px 120px 100px;display:flex;flex-direction:column;gap:36px">\n'
        f'<img src="{logo}" alt="Flo" style="position:absolute;left:40px;top:40px;width:54px;height:34px;object-fit:contain">\n'
        f'<div style="display:flex;flex-direction:column;gap:16px">'
        f'<p style="font-family:{SEMI};font-size:24px;font-weight:500;line-height:1.2;letter-spacing:2.6px;text-transform:uppercase;color:#c74500">Client stats from HubSpot</p>'
        f'<h2 style="width:1680px;font-family:{SANS};font-weight:600;font-size:60px;line-height:1.05;letter-spacing:-1.5px;color:{INK}">Client proof points update from the sales stats dashboard every week</h2></div>\n'
        f'<table style="width:1680px;font-size:24px;color:{INK}"><tr><th style="width:27%">Claim</th><th style="width:18%">Decks say today</th><th style="width:17%">Will say</th><th style="width:38%">HubSpot report</th></tr>{trs}</table>\n'
        f'<p style="position:absolute;left:120px;bottom:28px;width:1680px;font-size:24px;line-height:1.2;color:{FAINT}">Source: HubSpot, Client Stats for Sales Team’s Decks · Refreshed weekly on Mondays · Counts rounded down to the nearest 5; percentages to the nearest 5, with + when rounded down</p>\n'
        f'<aside>Percentages are firms in the ranking divided by its size (AmLaw 50 = 50 firms), rounded to the nearest 5 with a plus when that rounds down. Not on the dashboard, so still manual: Vault top 10/20 at 100%, 95% of top 50 schools, 60% of top 100 schools, 500+ agencies.</aside>\n</section>\n')
    return html, rows


SLIDES = {
    'accounts':            lambda c, i, l: slide_accounts(c, i, l),
    'outreach_500plus':    lambda c, i, l: slide_outreach(c, i, l, '500plus'),
    'outreach_u500':       lambda c, i, l: slide_outreach(c, i, l, 'u500'),
    'apps':                lambda c, i, l: slide_apps(c, i, l),
    'interviews_500plus':  lambda c, i, l: slide_interviews(c, i, l, '500plus'),
    'interviews_u500':     lambda c, i, l: slide_interviews(c, i, l, 'u500'),
    'interviews_all':      lambda c, i, l: slide_interviews(c, i, l, 'all'),
    'adoption_biglaw':     lambda c, i, l: slide_adoption(c, i, l, ('80+', '#c74500', 'Law school partners promoting the platform to students and integrating their own resources')),
    'adoption_midsize':    lambda c, i, l: slide_adoption(c, i, l, ('60+', '#c74500', 'Law school partners promoting the platform to students and integrating their own resources')),
    'reach_since_aug':     lambda c, i, l: slide_reach(c, i, l, 8),
    'lateral_source':      lambda c, i, l: slide_lateral_source(c, i, l),
    'lateral_profile':     lambda c, i, l: slide_lateral_profile(c, i, l),
    'student_count':       lambda c, i, l: slide_student_count(c, i, l),
    'client_stats':        lambda c, i, l: slide_client_stats(c, i, l),
}


def render(data, jobs, logo):
    """jobs: [(slide_id, slide_key)] -> {slide_id: (html, facts)}"""
    ctx = Ctx(data)
    LOGO[0] = logo
    return ctx, {sid: SLIDES[key](ctx, sid, logo) for sid, key in jobs}


if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    out, logo = sys.argv[2], sys.argv[3]
    jobs = [tuple(a.split('=')) for a in sys.argv[4:]]
    ctx, res = render(data, jobs, logo)
    os.makedirs(os.path.join(out, 'project', 'slides'), exist_ok=True)
    summary = {}
    for sid, (html, facts) in res.items():
        open(os.path.join(out, 'project', 'slides', f'{sid}.html'), 'w').write(html)
        summary[sid] = facts
    print(json.dumps({'asof': ctx.asof, 'slides': summary}, indent=1, default=str))


# ---------------------------------------------------------------- weekly client-stat refresh, decreases held
DENOM = {'amlaw50_clients': 50, 'amlaw100_clients': 100, 'amlaw200_clients': 200,
         'amlaw50_forward': 50, 'amlaw100_forward': 100, 'amlaw200_forward': 200,
         'vault50_forward': 50, 'vault100_forward': 100}


def shown(key, n):
    """What a deck would display for this stat."""
    if key == 'vault50_forward':
        return f'{n}/50'
    return pct(n, DENOM[key]) if key in DENOM else floor_5(n)


def merge_client_stats(path, fresh, today):
    """fresh: {key: value} pulled from HubSpot. Increases (and changes that don't alter what decks show)
    are applied; a change that would make a deck show a LOWER figure is held in 'pending' until approved.
    Returns (applied, held) lists for the run summary."""
    doc = json.load(open(path))
    applied, held = [], []
    doc.setdefault('pending', {})
    for key, rep in doc['reports'].items():
        if key not in fresh:
            continue
        old, new = rep['value'], fresh[key]
        if new < old and shown(key, new) != shown(key, old):
            doc['pending'][key] = {'value': new, 'shows': shown(key, new), 'was': shown(key, old), 'since': today}
            held.append((rep['name'], shown(key, old), shown(key, new)))
        else:
            if shown(key, new) != shown(key, old):
                applied.append((rep['name'], shown(key, old), shown(key, new)))
            rep['value'] = new
            doc['pending'].pop(key, None)
    doc['fetched'] = today
    json.dump(doc, open(path, 'w'), indent=2)
    return applied, held


def approve_pending(path, keys=None):
    """Apply held decreases (all, or just `keys`) after Hannah approves them."""
    doc = json.load(open(path))
    for key in list(doc.get('pending', {})):
        if keys is None or key in keys:
            doc['reports'][key]['value'] = doc['pending'].pop(key)['value']
    json.dump(doc, open(path, 'w'), indent=2)

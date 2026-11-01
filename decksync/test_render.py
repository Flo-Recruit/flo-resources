"""Unit tests for decksync's number patchers. Run: python3 decksync/test_render.py

These are deterministic: student_counts is stubbed so the test never depends on live
tracker data. They guard the student-count patch against the "and new graduates and new
graduates" doubling that happens when a slide splits the phrase across a line break.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render

# Fixed counts so expectations don't move with the tracker. floor_500 -> 51,500+ / 43,000+.
render.student_counts = lambda ctx: {
    'current': 43200, 'current_classes': (2026, 2028),
    'all': 51600, 'all_classes': (2024, 2028), 'by_class': {},
}
ALL, CUR = '51,500+', '43,000+'


def patch(html):
    out, _ = render.patch_student_count(html, None)
    return out


# (name, input, expected exact output)
EXACT = [
    ('contiguous new grads',    '51,000+ law students and new graduates',
                                f'{ALL} law students and new graduates'),
    ('contiguous early career', '51,000+ law students and early career associates',
                                f'{ALL} law students and new graduates'),
    ('split by newline',        '51,000+ law students\nand new graduates',
                                f'{ALL} law students\nand new graduates'),
    ('split by <br>',           '51,000+ law students<br>and new graduates',
                                f'{ALL} law students<br>and new graduates'),
    ('split by tags',           '51,000+ law students</span>\n  <span>and new graduates</span>',
                                f'{ALL} law students</span>\n  <span>and new graduates</span>'),
    ('bare, end of sentence',   '51,000+ law students.',
                                f'{ALL} law students and new graduates.'),
    ('bare, other follow-on',   '51,000+ law students use Flo',
                                f'{ALL} law students and new graduates use Flo'),
    ('current claim',           '51,000+ current law students',
                                f'{CUR} current law students'),
]


def main():
    failures = []
    for name, src, want in EXACT:
        got = patch(src)
        ok = got == want
        # invariant: a law-students claim must never end up with the tail twice
        if 'current' not in src and got.count('new graduates') != 1:
            ok = False
        print(f'  [{"ok" if ok else "FAIL":4}] {name:24} -> {" ".join(got.split())}')
        if not ok:
            failures.append((name, want, got))

    if failures:
        print('\nFAILURES:')
        for name, want, got in failures:
            print(f'  {name}\n    want: {want!r}\n    got:  {got!r}')
        print(f'\n{len(failures)} failed')
        sys.exit(1)
    print(f'\nall {len(EXACT)} student-count patch cases passed')


if __name__ == '__main__':
    main()

"""Generate every manuscript figure. Replaces the legacy 02_FIGURES.ipynb.

Rewritten as a script during R1, for two reasons. The convention is that revision
analyses are `.py`, never new `.ipynb`. And the notebook contained the defect
behind R1-Int-1:

    src_type = df.groupby(['source', 'race_type']).size().unstack()
    src_type.index = ['CoachCox', 'Official']     # <- positional, and wrong

`source` was read as a categorical, so groupby returns category order, not
alphabetical order — and the categories are created in order of first appearance
in the CSV, which begins with official records. The hardcoded list therefore
labelled official's bars "CoachCox" and vice versa, in panels (a) and (c) of
Figure 1. Panel (b) used `.rename(columns=...)`, matched by key, and was correct.
That is exactly the pattern of the published figure.

Every label mapping here goes through `_common.relabel`, which maps by key and
raises if any label is unmapped.

Changes against the submitted figures:
  Figure 1  sources correctly labelled (R1-Int-1); panel (c) gains T2
  Figure 2  transition panels in minutes rather than hours (R1-Rev2-Q21)
  Figure 3  T2 alongside T1 in all four panels (R1-Rev2-Q16, Q22)
  Figure 4  2026 marked as a partial season, COVID-19 period labelled precisely
            (R1-Rev2-Q11, Q24)
  Figure 5  new — participation by sex over time, as composition (R1-Rev2-Q23)

Figure 5 is deliberately descriptive. A resource description that is read as an
empirical study invites the wrong criticism, so this figure shows composition and
the Results text does not interpret it.

NOTE: final exports belong after the code audit. Running this before
then produces drafts for inspection, not bundle artefacts.

Run:  uv run --no-project --with pandas --with matplotlib --with seaborn \
        python notebooks/generate_figures.py
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from PIL import Image

import _common as C

matplotlib.use('Agg')
sns.set_theme(style='whitegrid', palette='muted', font_scale=1.1)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.dpi'] = 150

USECOLS = ['age_group', 'swim_sec', 't1_sec', 'bike_sec', 't2_sec', 'run_sec',
           'overall_sec', 'finish_status', 'awa_points', 'total_distance_km',
           'race_type', 'race_year', 'source']


def save(fig, name: str) -> None:
    """Write a publication TIFF: RGB, white background, LZW, 300 DPI.

    Journal figure requirements call for RGB with an opaque white background and
    LZW compression; matplotlib's TIFF writer emits RGBA by default, and the
    legacy notebook additionally asked for deflate. Every figure in the submitted
    bundle is RGBA — an alpha channel a typesetter may composite against
    anything, including black.
    """
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = C.FIG_DIR / name
    fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white',
                pil_kwargs={'compression': 'tiff_lzw'})
    # matplotlib still writes an alpha channel; flatten it onto white.
    with Image.open(path) as im:
        if im.mode != 'RGB':
            flat = Image.new('RGB', im.size, 'white')
            flat.paste(im, mask=im.split()[-1] if im.mode in ('RGBA', 'LA') else None)
            flat.save(path, compression='tiff_lzw', dpi=(300, 300))
    with Image.open(path) as im:
        assert im.mode == 'RGB', f'{name} is {im.mode}, expected RGB'
        mb = path.stat().st_size / 1024 ** 2
        assert mb < 10, f'{name} is {mb:.1f} MB, over the 10 MB publisher limit'
        print(f'  -> {path.name} ({path.stat().st_size / 1024:.0f} KB, {im.mode}, '
              f'{im.size[0]}x{im.size[1]})')
    plt.close(fig)


def hms(seconds: float) -> str:
    s = int(seconds)
    return f'{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}'


def panel_tag(ax, tag: str) -> None:
    ax.text(0.02, 0.95, tag, transform=ax.transAxes, fontsize=13,
            fontweight='bold', va='top')


def mark_partial_season(ax, years) -> None:
    """Flag the final season as incomplete wherever a year axis is drawn."""
    if C.PARTIAL_SEASON not in list(years):
        return
    ax.axvline(C.PARTIAL_SEASON, color='gray', ls=':', lw=1.2)
    ax.annotate(f'{C.PARTIAL_SEASON} partial', xy=(C.PARTIAL_SEASON, 0.02),
                xycoords=('data', 'axes fraction'), rotation=90,
                ha='right', va='bottom', fontsize=8, color='gray')


def year_frame(df):
    m = df.race_year.notna() & (df.race_year >= 2002) & (df.race_year <= C.PARTIAL_SEASON)
    return df[m]


# --------------------------------------------------------------------------- 1
def figure1(df) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    src_type = df.groupby(['source', 'race_type']).size().unstack(fill_value=0)
    src_type = C.relabel(src_type, C.SOURCE_LABELS, axis=0)
    src_type = C.relabel(src_type, C.RACE_TYPE_LABELS, axis=1)
    src_type = src_type.loc[[C.LABEL_OFFICIAL, C.LABEL_SUPPLEMENTARY]]
    src_type.plot.bar(ax=axes[0], color=[C.COLOR_HIM, C.COLOR_IM])
    axes[0].legend(title='Race Type')
    axes[0].set_ylabel('Records')
    axes[0].set_xlabel('Source')
    axes[0].tick_params(axis='x', rotation=0)
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f'{x / 1e6:.1f}M' if x >= 1e6 else f'{x / 1e3:.0f}K'))
    panel_tag(axes[0], '(a)')

    dy = year_frame(df)
    yearly = dy.groupby(['race_year', 'source']).size().unstack(fill_value=0)
    yearly = C.relabel(yearly, C.SOURCE_LABELS, axis=1)
    yearly[[C.LABEL_OFFICIAL, C.LABEL_SUPPLEMENTARY]].plot.area(
        ax=axes[1], color=[C.COLOR_OFFICIAL, C.COLOR_SUPPLEMENTARY], alpha=0.85)
    axes[1].legend(title='Source')
    axes[1].set_ylabel('Records')
    axes[1].set_xlabel('')
    mark_partial_season(axes[1], yearly.index)
    panel_tag(axes[1], '(b)')

    cov = df.groupby('source')[['has_t1', 'has_t2']].mean().mul(100)
    cov = C.relabel(cov, C.SOURCE_LABELS, axis=0)
    cov = cov.loc[[C.LABEL_OFFICIAL, C.LABEL_SUPPLEMENTARY]]
    cov = C.relabel(cov, {'has_t1': 'T1', 'has_t2': 'T2'}, axis=1)
    cov.plot.bar(ax=axes[2], color=[C.COLOR_T1, C.COLOR_T2])
    axes[2].set_ylabel('% with transition data')
    axes[2].set_ylim(0, 100)
    axes[2].set_xlabel('Source')
    axes[2].tick_params(axis='x', rotation=0)
    for container in axes[2].containers:
        axes[2].bar_label(container, fmt='%.1f%%', fontsize=9, padding=2)
    panel_tag(axes[2], '(c)')

    fig.tight_layout()
    save(fig, 'Figure1.tiff')


# --------------------------------------------------------------------------- 2
def figure2(df) -> None:
    """Transitions in minutes; the other four disciplines stay in hours."""
    fin = df[(df.race_type == 'im') & (df.finish_status == 'FIN')]
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    spec = [
        ('swim_sec', 'Swim', 'hours', (0.4, 2.6), C.COLOR_IM),
        ('t1_sec', 'T1', 'minutes', (0, 30), C.COLOR_HIM),
        ('bike_sec', 'Bike', 'hours', (3.5, 10.0), C.COLOR_IM),
        ('t2_sec', 'T2', 'minutes', (0, 30), C.COLOR_HIM),
        ('run_sec', 'Run', 'hours', (2.0, 8.5), C.COLOR_IM),
        ('overall_sec', 'Overall', 'hours', (7.0, 17.0), C.COLOR_IM),
    ]
    for ax, (col, label, unit, xlim, color), tag in zip(
            axes.flat, spec, ['(a)', '(b)', '(c)', '(d)', '(e)', '(f)']):
        raw = fin[col]
        raw = raw[raw > 0]
        divisor = 60 if unit == 'minutes' else 3600
        data = raw / divisor
        ax.hist(data, bins=80, range=xlim, color=color, alpha=0.7,
                edgecolor='white', linewidth=0.3)
        ax.axvline(data.median(), color='black', ls='--', lw=1.5,
                   label=f'Median: {hms(raw.median())}')
        ax.set_xlim(xlim)
        ax.set_xlabel('Minutes' if unit == 'minutes' else 'Hours')
        ax.set_ylabel('Count')
        ax.legend(fontsize=9, loc='upper right')
        # Report the count actually drawn. `range=` clips the tail, and the
        # submitted figure labelled each panel with the unclipped n — so a reader
        # saw a total that the histogram did not contain (audit A1-02). The median
        # line is still computed over the full distribution; the caption says so.
        shown = int(((data >= xlim[0]) & (data <= xlim[1])).sum())
        clipped = len(raw) - shown
        tag_text = f'{tag} {label} (n={shown:,}'
        tag_text += f'; {clipped:,} outside axis)' if clipped else ')'
        panel_tag(ax, tag_text)

    fig.tight_layout()
    save(fig, 'Figure2.tiff')


# --------------------------------------------------------------------------- 3
def figure3(df) -> None:
    """T1 and T2 side by side in every panel — the paper's contribution is both."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    dy = year_frame(df)

    by_year = dy.groupby('race_year')[['has_t1', 'has_t2']].mean().mul(100)
    for col, color, lab in (('has_t1', C.COLOR_T1, 'T1'), ('has_t2', C.COLOR_T2, 'T2')):
        axes[0, 0].plot(by_year.index, by_year[col], 'o-', color=color, lw=2,
                        markersize=4, label=lab)
    axes[0, 0].set_ylabel('% with transition data')
    axes[0, 0].set_ylim(0, 100)
    axes[0, 0].legend(fontsize=9)
    mark_partial_season(axes[0, 0], by_year.index)
    panel_tag(axes[0, 0], '(a)')

    for src, style in (('official', '-'), ('coachcox', '--')):
        g = dy[dy.source == src].groupby('race_year')[['has_t1', 'has_t2']].mean().mul(100)
        for col, color, lab in (('has_t1', C.COLOR_T1, 'T1'), ('has_t2', C.COLOR_T2, 'T2')):
            axes[0, 1].plot(g.index, g[col], style, color=color, lw=1.8,
                            label=f'{lab} — {C.SOURCE_LABELS[src]}')
    axes[0, 1].set_ylabel('% with transition data')
    axes[0, 1].set_ylim(0, 100)
    axes[0, 1].legend(fontsize=8)
    mark_partial_season(axes[0, 1], by_year.index)
    panel_tag(axes[0, 1], '(b)')

    by_type = df.groupby('race_type')[['has_t1', 'has_t2']].mean().mul(100)
    by_type = C.relabel(by_type, C.RACE_TYPE_LABELS, axis=0)
    by_type = C.relabel(by_type, {'has_t1': 'T1', 'has_t2': 'T2'}, axis=1)
    by_type.plot.bar(ax=axes[1, 0], color=[C.COLOR_T1, C.COLOR_T2])
    axes[1, 0].set_ylabel('% with transition data')
    axes[1, 0].set_ylim(0, 100)
    axes[1, 0].set_xlabel('Race type')
    axes[1, 0].tick_params(axis='x', rotation=0)
    for c in axes[1, 0].containers:
        axes[1, 0].bar_label(c, fmt='%.1f%%', fontsize=8, padding=2)
    panel_tag(axes[1, 0], '(c)')

    by_status = df.groupby('finish_status')[['has_t1', 'has_t2']].mean().mul(100)
    by_status = C.relabel(by_status, {'has_t1': 'T1', 'has_t2': 'T2'}, axis=1)
    by_status.plot.bar(ax=axes[1, 1], color=[C.COLOR_T1, C.COLOR_T2])
    axes[1, 1].set_ylabel('% with transition data')
    axes[1, 1].set_ylim(0, 100)
    axes[1, 1].set_xlabel('Finish status')
    axes[1, 1].tick_params(axis='x', rotation=0)
    for c in axes[1, 1].containers:
        axes[1, 1].bar_label(c, fmt='%.1f%%', fontsize=8, padding=2)
    panel_tag(axes[1, 1], '(d)')

    fig.tight_layout()
    save(fig, 'Figure3.tiff')


# --------------------------------------------------------------------------- 4
def figure4(df) -> None:
    dy = year_frame(df)
    fin = dy[(dy.race_type == 'im') & (dy.finish_status == 'FIN')]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    yearly = dy.groupby(['race_year', 'race_type']).size().unstack(fill_value=0)
    yearly = C.relabel(yearly, C.RACE_TYPE_LABELS, axis=1)
    yearly.plot.area(ax=axes[0, 0], color=[C.COLOR_HIM, C.COLOR_IM], alpha=0.85)
    axes[0, 0].legend(title='Race Type')
    axes[0, 0].set_ylabel('Records')
    axes[0, 0].set_xlabel('')
    mark_partial_season(axes[0, 0], yearly.index)
    panel_tag(axes[0, 0], '(a)')

    med = fin.groupby('race_year').overall_sec.median() / 3600
    axes[0, 1].plot(med.index, med.values, 'o-', color=C.COLOR_IM, lw=2, markersize=4)
    axes[0, 1].set_ylabel('Hours')
    axes[0, 1].axvspan(*C.COVID_SPAN, alpha=0.12, color=C.COLOR_COVID, label=C.COVID_LABEL)
    axes[0, 1].legend(fontsize=9)
    mark_partial_season(axes[0, 1], med.index)
    panel_tag(axes[0, 1], '(b)')

    starters = dy[dy.finish_status.isin(['FIN', 'DNF', 'DQ'])]
    dnf = (starters.assign(is_dnf=starters.finish_status == 'DNF')
           .groupby(['race_year', 'race_type']).is_dnf.mean().unstack() * 100)
    dnf = C.relabel(dnf, C.RACE_TYPE_LABELS, axis=1)
    for col, color, marker in ((C.LABEL_IM, C.COLOR_IM, 'o'),
                               (C.LABEL_HIM, C.COLOR_HIM, 's')):
        if col in dnf.columns:
            axes[1, 0].plot(dnf.index, dnf[col], f'{marker}-', color=color, lw=2,
                            markersize=4, label=col)
    axes[1, 0].set_ylabel('DNF (%)')
    axes[1, 0].axvspan(*C.COVID_SPAN, alpha=0.12, color=C.COLOR_COVID, label=C.COVID_LABEL)
    axes[1, 0].legend(fontsize=9)
    mark_partial_season(axes[1, 0], dnf.index)
    panel_tag(axes[1, 0], '(c)')

    fem = dy.groupby('race_year').gender.apply(lambda s: (s == 'Female').mean() * 100)
    axes[1, 1].plot(fem.index, fem.values, 'o-', color=C.COLOR_HIM, lw=2, markersize=4)
    axes[1, 1].fill_between(fem.index, fem.values, alpha=0.15, color=C.COLOR_HIM)
    axes[1, 1].set_ylabel('Female (%)')
    axes[1, 1].axvspan(*C.COVID_SPAN, alpha=0.12, color=C.COLOR_COVID, label=C.COVID_LABEL)
    axes[1, 1].legend(fontsize=9)
    mark_partial_season(axes[1, 1], fem.index)
    panel_tag(axes[1, 1], '(d)')

    fig.tight_layout()
    save(fig, 'Figure4.tiff')


# --------------------------------------------------------------------------- 5
def figure5(df) -> None:
    """Participation by sex over time. Composition, not trend analysis."""
    dy = year_frame(df)
    counts = (dy[dy.gender.isin(['Male', 'Female'])]
              .groupby(['race_year', 'gender']).size().unstack(fill_value=0))
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))

    counts[['Male', 'Female']].plot.area(
        ax=axes[0], color=[C.COLOR_IM, C.COLOR_HIM], alpha=0.85)
    axes[0].set_ylabel('Records')
    axes[0].set_xlabel('')
    axes[0].legend(title='Sex')
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, _: f'{x / 1e3:.0f}K'))
    mark_partial_season(axes[0], counts.index)
    panel_tag(axes[0], '(a)')

    by_type = (dy[dy.gender.isin(['Male', 'Female'])]
               .groupby(['race_year', 'race_type']).gender
               .apply(lambda s: (s == 'Female').mean() * 100).unstack())
    by_type = C.relabel(by_type, C.RACE_TYPE_LABELS, axis=1)
    for col, color in ((C.LABEL_IM, C.COLOR_IM), (C.LABEL_HIM, C.COLOR_HIM)):
        if col in by_type.columns:
            axes[1].plot(by_type.index, by_type[col], 'o-', color=color, lw=2,
                         markersize=4, label=col)
    axes[1].set_ylabel('Female share (%)')
    axes[1].set_xlabel('')
    axes[1].legend(title='Race Type', fontsize=9)
    mark_partial_season(axes[1], by_type.index)
    panel_tag(axes[1], '(b)')

    fig.tight_layout()
    save(fig, 'Figure5.tiff')


def main() -> None:
    print('loading...')
    df = C.load(usecols=USECOLS)
    print(f'  {len(df):,} records\n')

    # Guards against the two classes that bit us. Both are cheap; both would have
    # caught a defect that reached a submitted figure.
    composition = df.groupby('source', observed=True).size()
    assert composition['official'] > composition['coachcox'], (
        'official should be the majority source (75.4/24.6); '
        'check the source column before trusting any figure')
    print('source composition check passed: '
          f'official {composition["official"]:,} > coachcox {composition["coachcox"]:,}')

    # Coverage must be computed over ALL records. If has_t1 were left as nullable
    # boolean, .mean() would skip the NAs and inflate every coverage figure.
    for col, expected in (('has_t1', 84.19), ('has_t2', 84.09)):
        actual = df[col].mean() * 100
        assert abs(actual - expected) < 0.1, (
            f'{col} coverage is {actual:.2f}%, expected ~{expected}%. '
            'A nullable-boolean mean would skip missing values and inflate this.')
    print(f'coverage denominator check passed: T1 {df.has_t1.mean() * 100:.2f}%, '
          f'T2 {df.has_t2.mean() * 100:.2f}%\n')

    for fn in (figure1, figure2, figure3, figure4, figure5):
        print(f'{fn.__name__}...')
        fn(df)
    print('\ndone. Final exports belong after the code audit.')


if __name__ == '__main__':
    main()

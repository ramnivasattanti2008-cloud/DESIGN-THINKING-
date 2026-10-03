# -*- coding: utf-8 -*-
"""
Figure 1 for the BHARAT-SCAM-X paper.
Every number is read from results/results.json -- nothing is hand-entered.
"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results", "results.json")
OUT = os.path.join(HERE, "..", "paper", "fig1_gap.pdf")

# Validated categorical slots 1-3 (all-pairs, light surface)
C = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#d8d7d2"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "font.size": 9,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
})

R = json.load(open(RES))
MODELS = ["Keyword-Rule", "TFIDF-Word-LR", "TFIDF-Char-LR", "Struct-Sig-Char"]
SHORT = ["Keyword\nrule", "TF-IDF\nword", "TF-IDF\nchar", "Struct-Sig\n(ours)"]

panel_a = {
    "In-distribution $F_1$": [R["binary"][m]["IID"]["f1"] for m in MODELS],
    "Cross-lingual $F_1$":   [R["binary"][m]["Cross-ling"]["f1"] for m in MODELS],
    "Flip-success rate":     [R["sfs"][m]["flip_success"] for m in MODELS],
}
panel_b = {
    "FPR, hard negatives":  [R["fpr"][m]["hard_negative"] for m in MODELS],
    "FPR, semantic flips":  [R["fpr"][m]["sfs_flip"] for m in MODELS],
}

fig, axes = plt.subplots(1, 2, figsize=(7.9, 3.15))
x = np.arange(len(MODELS))


def draw(ax, data, title, note):
    k = len(data)
    w = 0.78 / k
    for i, (label, vals) in enumerate(data.items()):
        off = (i - (k - 1) / 2) * w
        bars = ax.bar(x + off, vals, w * 0.90, label=label,
                      color=C[i], edgecolor=SURFACE, linewidth=1.2, zorder=3)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.022, f"{v:.2f}",
                    ha="center", va="bottom", fontsize=6.1, color=INK2, zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(SHORT, fontsize=7.6)
    ax.set_ylim(0, 1.16)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title(title, fontsize=8.8, pad=9, loc="left", color=INK)
    ax.set_ylabel(note, fontsize=7.3, color=INK2, labelpad=3)
    ax.legend(frameon=False, fontsize=6.9, loc="upper center",
              bbox_to_anchor=(0.5, -0.17), ncol=k, handlelength=1.1,
              columnspacing=1.1, handletextpad=0.45)


draw(axes[0], panel_a, "(a) Detection and flip sensitivity", "higher is better")
draw(axes[1], panel_b, "(b) False positives on benign text", "lower is better")

plt.tight_layout(rect=[0, 0.02, 1, 0.98])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
plt.savefig(OUT, bbox_inches="tight", facecolor=SURFACE)
plt.savefig(OUT.replace(".pdf", ".png"), dpi=220, bbox_inches="tight", facecolor=SURFACE)
print("wrote", OUT)

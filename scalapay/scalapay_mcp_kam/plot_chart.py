import matplotlib
matplotlib.use("Agg")  # Headless backend for AWS Lambda

data = {
    "Jan": {2023: 15, 2024: 41, 2025: 46},
    "Feb": {2023: 11, 2024: 31, 2025: 52},
    "Mar": {2023: 10, 2024: 44, 2025: 52},
    "Apr": {2023: 42, 2024: 31, 2025: 47},
    "May": {2023: 59, 2024: 43, 2025: 44},
    "Jun": {2023: 61, 2024: 41, 2025: 29},
    "Jul": {2023: 28, 2024: 28},
    "Aug": {2023: 39, 2024: 36},
    "Sep": {2023: 34, 2024: 31},
    "Oct": {2022: 6, 2023: 45, 2024: 25},
    "Nov": {2022: 21, 2023: 36, 2024: 36},
    "Dec": {2022: 14, 2023: 27, 2024: 16}
}

def plot_monthly_sales_chart(data: dict, output_path="/mnt/data/dynamic_chart_colored.png"):
    import matplotlib.pyplot as plt
    import numpy as np

    months = list(data.keys())
    years = sorted(set(year for month in data.values() for year in month))

    # Dynamically assign distinct colors to years using a fixed color palette
    color_palette = [
        "#8ad3f4", "#d896f6", "#f7a463", "#f15375", "#b7b8f5", "#f6b8ea",
        "#469acf", "#ffd700", "#b0e0e6", "#ffa07a"
    ]
    colors_by_year = {year: color_palette[i % len(color_palette)] for i, year in enumerate(years)}

    x = np.arange(len(months))
    width = 0.8 / len(years)

    # Set size in inches
    fig_width_inch = 12
    fig_height_inch = 4
    dpi = 150

    fig, ax = plt.subplots(figsize=(fig_width_inch, fig_height_inch))

    for i, year in enumerate(years):
        values = [data[month].get(year, 0) for month in months]
        offsets = x + i * width
        bars = ax.bar(offsets, values, width, label=str(year), color=colors_by_year[year])
        for offset, value in zip(offsets, values):
            if value > 0:
                ax.text(offset, value + 1, str(value), ha='center', va='bottom', fontsize=7)

    ax.set_xticks(x + width * (len(years) - 1) / 2)
    ax.set_xticklabels(months)
    ax.set_ylabel("Sales")
    ax.legend(title="Year")
    ax.set_ylim(0, max(max(month.values()) for month in data.values()) + 10)

    fig.tight_layout()
    plt.savefig(output_path, dpi=dpi)
    plt.close(fig)

    # Compute pixel dimensions
    width_px = int(fig_width_inch * dpi)
    height_px = int(fig_height_inch * dpi)

    return output_path, width_px, height_px

if __name__ == "__main__":
    # Example usage

    plot_monthly_sales_chart(data, output_path="/tmp/chart.png")

    output_path = "/tmp/chart.png"
    print(f"Chart saved to {output_path}")
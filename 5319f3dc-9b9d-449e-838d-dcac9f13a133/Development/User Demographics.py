

# Branches off "Example Dataset". Pulls demographic columns out of `df` so
# downstream visualization blocks don't need the full 2.7GB DataFrame.

demographics = {
    "browser":     df["properties.$browser"].value_counts().head(8),
    "country":     df["properties.$geoip_country_name"].value_counts().head(10),
    "device_type": df["properties.$device_type"].value_counts().head(6),
    "os":          df["properties.$os"].value_counts().head(8),
}

for name, vc in demographics.items():
    print(f"--- top {name} ---")
    print(vc.to_string())
    print()
